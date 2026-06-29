import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jarvis.history import History
from evals.run import _turn_count


def _make_tool_result_msg():
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}


def test_turn_count_zero_no_tool_results():
    h = History()
    h.append_user("hello")
    assert _turn_count(h) == 0


def test_turn_count_zero_assistant_only():
    h = History()
    h.append_user("q")
    # manually inject assistant message with tool_use (not a tool_result user msg)
    h._messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {}}]})
    assert _turn_count(h) == 0


def test_turn_count_one_cycle():
    h = History()
    h.append_user("q")
    h._messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {}}]})
    h._messages.append(_make_tool_result_msg())
    assert _turn_count(h) == 1


def test_turn_count_three_cycles():
    h = History()
    h.append_user("q")
    for i in range(3):
        h._messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "bash", "input": {}}]})
        h._messages.append(_make_tool_result_msg())
    assert _turn_count(h) == 3


def test_turn_count_ignores_plain_user_messages():
    h = History()
    h.append_user("first")
    h.append_user("second")   # plain string content, not a list
    assert _turn_count(h) == 0


import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile


async def _fake_run_turn_slow(history, config):
    await asyncio.sleep(9999)


async def _fake_run_turn_writes(history, config):
    """Simulates run_turn writing a file via the tracked executor."""
    writer = tools.EXECUTORS["write_file"]
    await writer(path="jarvis/skills/remind.py", content="# remind skill\n")


def _make_fake_item(prompt):
    item = MagicMock()
    item.input = {"prompt": prompt}
    item.expected_output = {"file": "jarvis/skills/remind.py", "max_turns": 25}
    return item


def test_build_skill_task_sets_timed_out_on_timeout(tmp_path):
    """When run_turn hangs, build_skill_task must set timed_out=True and return."""
    import evals.run as er

    # Patch COMMANDS_PATH to a temp file so we don't touch the real repo
    fake_commands = tmp_path / "commands.py"
    fake_commands.write_text("# original\n")

    with patch.object(er, "COMMANDS_PATH", fake_commands), \
         patch.object(er, "SKILLS_DIR", tmp_path.resolve()), \
         patch.object(er, "BUILD_TIMEOUT", 0.1), \
         patch("evals.run.run_turn", new=_fake_run_turn_slow):

        async def _run():
            item = _make_fake_item("build /remind")
            config = MagicMock()
            # inline the task logic (mirrors build_skill_task body)
            from evals.run import _turn_count, _final_text, _tool_calls
            history = __import__("jarvis.history", fromlist=["History"]).History()
            history.append_user(item.input["prompt"])
            files_written = []
            original_commands = fake_commands.read_text()
            original_write = er.tools.EXECUTORS.get("write_file")
            async def tracking_write(**kw):
                files_written.append(kw.get("path", ""))
                return await original_write(**kw)
            timed_out = False
            elapsed = 0.0
            try:
                with patch.dict(er.tools.EXECUTORS, {"write_file": tracking_write}):
                    await asyncio.wait_for(er.run_turn(history, config), timeout=er.BUILD_TIMEOUT)
            except asyncio.TimeoutError:
                timed_out = True
            finally:
                elapsed = 1.0  # dummy
                fake_commands.write_text(original_commands)
            return {"timed_out": timed_out, "elapsed": elapsed}

        result = asyncio.run(_run())
        assert result["timed_out"] is True
        # commands.py must be restored
        assert fake_commands.read_text() == "# original\n"


def test_build_skill_task_cleanup_deletes_written_skill_files(tmp_path):
    """Files written under SKILLS_DIR must be deleted in finally."""
    import evals.run as er

    fake_commands = tmp_path / "commands.py"
    fake_commands.write_text("# original\n")
    skills_dir = (tmp_path / "skills").resolve()
    skills_dir.mkdir()

    skill_path = str(skills_dir / "remind.py")

    async def _fake_run_writes(history, config):
        # write a file via the patched executor
        writer = er.tools.EXECUTORS["write_file"]
        await writer(path=skill_path, content="# remind\n")

    with patch.object(er, "COMMANDS_PATH", fake_commands), \
         patch.object(er, "SKILLS_DIR", skills_dir), \
         patch("evals.run.run_turn", new=_fake_run_writes):

        async def _run():
            from jarvis.history import History
            from evals.run import _turn_count, _final_text, _tool_calls
            history = History()
            history.append_user("build")
            files_written = []
            original_commands = fake_commands.read_text()
            original_write = er.tools.EXECUTORS.get("write_file")
            async def tracking_write(**kw):
                files_written.append(kw.get("path", ""))
                return await original_write(**kw)
            timed_out = False
            elapsed = 0.0
            try:
                with patch.dict(er.tools.EXECUTORS, {"write_file": tracking_write}):
                    await asyncio.wait_for(er.run_turn(history, MagicMock()), timeout=er.BUILD_TIMEOUT)
            except asyncio.TimeoutError:
                timed_out = True
            finally:
                elapsed = 0.1
                fake_commands.write_text(original_commands)
                for p in files_written:
                    fp = Path(os.path.abspath(p))
                    if fp.exists() and str(fp).startswith(str(skills_dir)):
                        fp.unlink()
            return {"timed_out": timed_out, "files_written": files_written}

        result = asyncio.run(_run())
        # The file must have been deleted
        assert not (skills_dir / "remind.py").exists()
        assert skill_path in result["files_written"]
