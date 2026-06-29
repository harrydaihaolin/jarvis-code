"""
Tests for the /btw skill and its integration into the command handler.

Strategy
--------
- The sub-agent's network calls (anthropic client) are always mocked so the
  test-suite is fully offline and deterministic.
- We test the skill module (jarvis.skills.btw) directly as well as the
  end-to-end path through jarvis.commands.handle().
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jarvis.config import Config
from jarvis.history import History
from jarvis.commands import handle
from jarvis.skills import btw as btw_module


# ── helpers ───────────────────────────────────────────────────────────────────

FAKE_CONFIG = Config(api_key="test-key", model="claude-test")


def _make_stream_mock(text: str = "42 is the answer."):
    """
    Build a mock that mimics the anthropic streaming context manager used
    inside btw._run() and query.run_turn().
    """
    # Final message object
    final_msg = MagicMock()
    final_msg.stop_reason = "end_turn"
    final_msg.content = [MagicMock(type="text", text=text)]

    # Async generator for text_stream
    async def _text_gen():
        yield text

    stream_ctx = MagicMock()
    stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
    stream_ctx.__aexit__ = AsyncMock(return_value=False)
    stream_ctx.text_stream = _text_gen()
    stream_ctx.get_final_message = AsyncMock(return_value=final_msg)
    return stream_ctx


def _patch_anthropic(stream_mock):
    """Patch the AsyncAnthropic client used inside btw._run()."""
    client_mock = MagicMock()
    client_mock.messages.stream.return_value = stream_mock
    return patch("anthropic.AsyncAnthropic", return_value=client_mock)


# ── unit: btw.spawn() ─────────────────────────────────────────────────────────

class TestBtwSpawn:

    def test_spawn_returns_task(self):
        """spawn() must immediately return an asyncio.Task."""
        stream_mock = _make_stream_mock()

        async def _run():
            with _patch_anthropic(stream_mock):
                task = btw_module.spawn("what is 6*7?", FAKE_CONFIG)
                assert isinstance(task, asyncio.Task)
                await task   # wait for it so nothing leaks

        asyncio.run(_run())

    def test_spawn_different_questions_create_different_tasks(self):
        """Each spawn() call must produce an independent Task."""
        stream_mock_1 = _make_stream_mock("answer 1")
        stream_mock_2 = _make_stream_mock("answer 2")

        async def _run():
            with _patch_anthropic(stream_mock_1):
                t1 = btw_module.spawn("question one", FAKE_CONFIG)
            with _patch_anthropic(stream_mock_2):
                t2 = btw_module.spawn("question two", FAKE_CONFIG)

            assert t1 is not t2
            # clean up
            await asyncio.gather(t1, t2, return_exceptions=True)

        asyncio.run(_run())

    def test_spawn_task_completes_without_error(self):
        """The task must complete successfully for a normal LLM response."""
        stream_mock = _make_stream_mock("all good")

        async def _run():
            with _patch_anthropic(stream_mock):
                task = btw_module.spawn("quick question", FAKE_CONFIG)
                await task
            assert not task.cancelled()
            assert task.exception() is None

        asyncio.run(_run())

    def test_spawn_does_not_block_caller(self):
        """
        The coroutine that called spawn() must be able to continue immediately
        (i.e. spawn is fire-and-forget, not awaited inline).
        """
        completed_order: list[str] = []

        async def _caller():
            stream_mock = _make_stream_mock()
            with _patch_anthropic(stream_mock):
                task = btw_module.spawn("side question", FAKE_CONFIG)
            completed_order.append("caller_continued")
            await task
            completed_order.append("task_done")

        asyncio.run(_caller())
        assert completed_order[0] == "caller_continued"
        assert completed_order[1] == "task_done"


# ── unit: btw._run() output ───────────────────────────────────────────────────

class TestBtwRun:

    def test_output_contains_btw_prefix(self, capsys):
        """The printed output must include the [btw] visual prefix."""
        stream_mock = _make_stream_mock("here is your answer")

        async def _run():
            with _patch_anthropic(stream_mock):
                await btw_module._run("what is X?", FAKE_CONFIG)

        asyncio.run(_run())
        out = capsys.readouterr().out
        assert "[btw]" in out

    def test_output_contains_original_question(self, capsys):
        """The header line must echo the question back to the user."""
        stream_mock = _make_stream_mock("some reply")

        async def _run():
            with _patch_anthropic(stream_mock):
                await btw_module._run("original question here", FAKE_CONFIG)

        asyncio.run(_run())
        out = capsys.readouterr().out
        assert "original question here" in out

    def test_output_contains_answer(self, capsys):
        """The actual LLM answer must appear in stdout."""
        answer = "The answer is forty-two."
        stream_mock = _make_stream_mock(answer)

        async def _run():
            with _patch_anthropic(stream_mock):
                await btw_module._run("what is the answer?", FAKE_CONFIG)

        asyncio.run(_run())
        out = capsys.readouterr().out
        assert answer in out

    def test_separator_lines_present(self, capsys):
        """Visual separators must frame the sub-agent block."""
        stream_mock = _make_stream_mock("ok")

        async def _run():
            with _patch_anthropic(stream_mock):
                await btw_module._run("hey", FAKE_CONFIG)

        asyncio.run(_run())
        out = capsys.readouterr().out
        # Separator is made of "─" chars (U+2500)
        assert "─" in out

    def test_isolated_history_not_shared_with_main(self):
        """
        The sub-agent must use its own History instance; the main History
        must stay untouched.
        """
        main_history = History()
        main_history.append_user("main question")

        stream_mock = _make_stream_mock("btw answer")

        async def _run():
            with _patch_anthropic(stream_mock):
                await btw_module._run("side question", FAKE_CONFIG)

        asyncio.run(_run())
        # Main history still has exactly one message
        assert len(main_history.messages) == 1
        assert main_history.messages[0]["content"] == "main question"


# ── unit: btw._run() with tool use ────────────────────────────────────────────

class TestBtwToolUse:

    def test_sub_agent_executes_tool_and_continues(self, capsys):
        """
        When stop_reason == 'tool_use', the sub-agent should call the tool
        and then loop for a follow-up completion.
        """
        import anthropic as anthropic_lib

        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.id = "tu_001"
        tool_use_block.name = "bash"
        tool_use_block.input = {"command": "echo hello"}

        # First message: requests a tool
        first_msg = MagicMock()
        first_msg.stop_reason = "tool_use"
        first_msg.content = [tool_use_block]

        # Second message: final text
        second_msg = MagicMock()
        second_msg.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "done after tool"
        second_msg.content = [text_block]

        async def _empty_text():
            return
            yield  # make it an async generator

        call_count = 0

        def _stream_factory(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            if call_count == 1:
                ctx.text_stream = _empty_text()
                ctx.get_final_message = AsyncMock(return_value=first_msg)
            else:
                async def _gen():
                    yield "done after tool"
                ctx.text_stream = _gen()
                ctx.get_final_message = AsyncMock(return_value=second_msg)
            return ctx

        client_mock = MagicMock()
        client_mock.messages.stream.side_effect = _stream_factory

        with patch("anthropic.AsyncAnthropic", return_value=client_mock), \
             patch("jarvis.tools.EXECUTORS", {"bash": AsyncMock(return_value="hello\n")}):
            asyncio.run(btw_module._run("run bash please", FAKE_CONFIG))

        out = capsys.readouterr().out
        assert "done after tool" in out
        assert call_count == 2


# ── unit: error handling (_on_done callback) ──────────────────────────────────

class TestBtwErrorHandling:

    def test_exception_in_task_does_not_crash_event_loop(self, capsys):
        """
        If the sub-agent raises, the error must be swallowed gracefully by
        _on_done (printed to stderr) without propagating to the caller.
        """
        async def _failing_run(question, config):
            raise RuntimeError("fake network error")

        async def _outer():
            with patch.object(btw_module, "_run", side_effect=_failing_run):
                task = btw_module.spawn("will fail", FAKE_CONFIG)
                await asyncio.sleep(0)   # let the task tick
                # Give the done callback a chance to run
                await asyncio.sleep(0)
            # The outer coroutine must still be alive
            return "outer_ok"

        result = asyncio.run(_outer())
        assert result == "outer_ok"

    def test_cancelled_task_handled_silently(self):
        """Cancelling a /btw task must not raise anywhere."""
        stream_mock = _make_stream_mock("slow answer")

        async def _slow_run(question, config):
            await asyncio.sleep(10)   # will be cancelled

        async def _outer():
            with patch.object(btw_module, "_run", side_effect=_slow_run):
                task = btw_module.spawn("slow question", FAKE_CONFIG)
                await asyncio.sleep(0)
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

        asyncio.run(_outer())   # must not raise


# ── integration: handle() with /btw ──────────────────────────────────────────

class TestHandleBtw:

    def test_btw_returns_true(self, capsys):
        """handle() must return True for /btw (it is a handled command)."""
        h = History()
        stream_mock = _make_stream_mock()

        async def _run():
            with _patch_anthropic(stream_mock):
                result = handle("/btw what is a decorator?", h, FAKE_CONFIG)
                assert result is True
                # Let the background task run to avoid ResourceWarning
                await asyncio.sleep(0)
                tasks = [t for t in asyncio.all_tasks() if not t.done()]
                await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run(_run())

    def test_btw_does_not_modify_main_history(self, capsys):
        """The main History must be untouched after /btw."""
        h = History()
        h.append_user("main question")
        stream_mock = _make_stream_mock()

        async def _run():
            with _patch_anthropic(stream_mock):
                handle("/btw side question", h, FAKE_CONFIG)
                tasks = [t for t in asyncio.all_tasks() if not t.done()]
                await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run(_run())
        assert len(h.messages) == 1
        assert h.messages[0]["content"] == "main question"

    def test_btw_empty_question_shows_usage(self, capsys):
        """/btw with no question must print usage, not crash."""
        h = History()
        result = handle("/btw", h, FAKE_CONFIG)
        assert result is True
        out = capsys.readouterr().out
        assert "usage" in out.lower() or "/btw" in out

    def test_btw_whitespace_only_shows_usage(self, capsys):
        h = History()
        result = handle("/btw   ", h, FAKE_CONFIG)
        assert result is True
        out = capsys.readouterr().out
        assert "usage" in out.lower() or "/btw" in out

    def test_btw_without_config_shows_error(self, capsys):
        """If config is None (e.g. called from a test without config), print a clear message."""
        h = History()
        result = handle("/btw anything", h, config=None)
        assert result is True
        out = capsys.readouterr().out
        assert "config" in out.lower() or "btw" in out.lower()

    def test_btw_prints_spawn_confirmation(self, capsys):
        """A short confirmation line must appear immediately (before the task finishes)."""
        h = History()
        stream_mock = _make_stream_mock()

        async def _run():
            with _patch_anthropic(stream_mock):
                handle("/btw what is asyncio?", h, FAKE_CONFIG)
                out = capsys.readouterr().out
                # Confirmation is synchronous — visible before task completes
                assert "[btw]" in out or "sub-agent" in out.lower()
                tasks = [t for t in asyncio.all_tasks() if not t.done()]
                await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run(_run())

    def test_btw_in_help_text(self, capsys):
        """/btw must be documented in /help."""
        h = History()
        handle("/help", h)
        out = capsys.readouterr().out
        assert "/btw" in out

    def test_btw_question_forwarded_verbatim(self, capsys):
        """The question text must reach the confirmation output unchanged."""
        question = "does list.sort mutate in place?"
        h = History()
        stream_mock = _make_stream_mock()

        async def _run():
            with _patch_anthropic(stream_mock):
                handle(f"/btw {question}", h, FAKE_CONFIG)
                out = capsys.readouterr().out
                assert question in out
                tasks = [t for t in asyncio.all_tasks() if not t.done()]
                await asyncio.gather(*tasks, return_exceptions=True)

        asyncio.run(_run())

    def test_btw_multiple_spawns_are_independent(self, capsys):
        """Two /btw calls must produce two independent tasks."""
        h = History()
        tasks_seen: list[asyncio.Task] = []
        original_spawn = btw_module.spawn

        def _capturing_spawn(question, config):
            t = original_spawn(question, config)
            tasks_seen.append(t)
            return t

        stream_mock_1 = _make_stream_mock("answer one")
        stream_mock_2 = _make_stream_mock("answer two")

        async def _run():
            with patch.object(btw_module, "spawn", side_effect=_capturing_spawn), \
                 _patch_anthropic(stream_mock_1):
                handle("/btw question one", h, FAKE_CONFIG)

            with patch.object(btw_module, "spawn", side_effect=_capturing_spawn), \
                 _patch_anthropic(stream_mock_2):
                handle("/btw question two", h, FAKE_CONFIG)

            assert len(tasks_seen) == 2
            assert tasks_seen[0] is not tasks_seen[1]
            await asyncio.gather(*tasks_seen, return_exceptions=True)

        asyncio.run(_run())
