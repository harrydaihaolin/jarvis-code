# Build-Skill Eval Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `build-skill-v1` eval item to `evals/run.py` that runs the "build /remind like /btw" prompt with a timeout + write-file tracker, captures turn count and files written, and evaluates completion, turn budget, and file creation — diagnosing the current hang.

**Architecture:** All changes are in `evals/run.py` and a new `tests/test_evals.py`. A second Langfuse dataset (`jarvis-build-skill`) and a second `lf.run_experiment` call are added alongside the existing sanity experiment. The `build_skill_task` function wraps `run_turn` with `asyncio.wait_for(timeout=120)`, patches `tools.EXECUTORS["write_file"]` to track every path written, and restores `commands.py` + deletes created skill files in a `finally` block. Three new evaluators score the output.

**Tech Stack:** Python 3.12, anthropic SDK, langfuse>=2.0.0, asyncio, pathlib, unittest.mock.patch

## Global Constraints

- Python ≥ 3.12
- No new source files — all changes in `evals/run.py` and `tests/test_evals.py`
- Do not modify `jarvis/query.py` or any source under `jarvis/` — eval-first, fix later
- `BUILD_TIMEOUT = 120` seconds
- `max_turns` threshold in expected_output = 25
- Target skill: `jarvis/skills/remind.py`; target dataset: `jarvis-build-skill`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `evals/run.py` | Modify | Add `_turn_count`, `_print_results`, constants, `build_skill_task`, three new evaluators, second experiment run |
| `tests/test_evals.py` | Create | Unit tests for `_turn_count` and the three new evaluator functions |

---

### Task 1: `_turn_count` helper + tests

**Files:**
- Modify: `evals/run.py`
- Create: `tests/test_evals.py`

**Interfaces:**
- Produces: `_turn_count(history: History) -> int` — counts user messages whose content list contains at least one `{"type": "tool_result"}` block

- [ ] **Step 1: Create `tests/test_evals.py` with failing tests**

```python
# tests/test_evals.py
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jarvis.history import History
from evals.run import _turn_count


def _make_tool_result_msg():
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}

def _make_user_msg(text="hi"):
    return {"role": "user", "content": text}

def _make_assistant_msg(text="hello"):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/test_evals.py -v 2>&1 | head -20
```

Expected: `ImportError` or `ModuleNotFoundError` for `_turn_count` (it doesn't exist yet).

- [ ] **Step 3: Add `_turn_count` to `evals/run.py`**

In `evals/run.py`, add after the `_final_text` function (around line 38):

```python
def _turn_count(history: History) -> int:
    """Count completed tool-use cycles (user messages that contain tool_result blocks)."""
    return sum(
        1
        for msg in history.messages
        if msg["role"] == "user"
        and isinstance(msg["content"], list)
        and any(b.get("type") == "tool_result" for b in msg["content"])
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/test_evals.py -v
```

Expected: 5 tests, all PASSED.

- [ ] **Step 5: Commit**

```bash
git add evals/run.py tests/test_evals.py
git commit -m "feat(evals): add _turn_count helper with tests"
```

---

### Task 2: Build-skill constants + `_print_results` refactor

**Files:**
- Modify: `evals/run.py`

**Interfaces:**
- Produces: constants `BUILD_DATASET`, `BUILD_TIMEOUT`, `COMMANDS_PATH`, `SKILLS_DIR`, `BUILD_PROMPT`
- Produces: `_print_results(label: str, result) -> None`

- [ ] **Step 1: Add imports and constants**

At the top of `evals/run.py`, update imports to:

```python
#!/usr/bin/env python3
"""Jarvis Code eval loop — sanity check via Langfuse self-hosted."""

import asyncio
import os
import time
from pathlib import Path
from unittest.mock import patch

from langfuse import Langfuse
from langfuse.experiment import Evaluation

from jarvis.config import load_config
from jarvis import tools
from jarvis.history import History
from jarvis.query import run_turn
```

Then add the build-skill constants block after the existing sanity constants:

```python
# ── build-skill eval constants ────────────────────────────────────────────────
BUILD_DATASET = "jarvis-build-skill"
BUILD_TIMEOUT = 120
_REPO_ROOT = Path(__file__).parent.parent
COMMANDS_PATH = _REPO_ROOT / "jarvis" / "commands.py"
SKILLS_DIR = (_REPO_ROOT / "jarvis" / "skills").resolve()
BUILD_PROMPT = (
    "Build a new skill called /remind, structured exactly like /btw. "
    "Create jarvis/skills/remind.py and register /remind in jarvis/commands.py."
)
```

- [ ] **Step 2: Extract `_print_results` helper**

In `evals/run.py`, add this function after `_turn_count`:

```python
def _print_results(label: str, result) -> None:
    print(f"\n--- {label} results ---")
    passed_count = 0
    for item_result in result.item_results:
        evals = item_result.evaluations or []
        passed = all(ev.value == 1.0 for ev in evals)
        elapsed = item_result.output.get("elapsed", 0) if item_result.output else 0
        for ev in evals:
            icon = "✓" if ev.value == 1.0 else "✗"
            print(f"  {icon} {ev.name}: {ev.comment}")
        print(f"  {'PASS' if passed else 'FAIL'}  ({elapsed:.1f}s)")
        if passed:
            passed_count += 1
    total = len(result.item_results)
    print(f"\n{passed_count}/{total} passed")
    if result.dataset_run_url:
        print(f"View: {result.dataset_run_url}")
    else:
        print(f"View: {LANGFUSE_HOST}")
```

Then replace the existing inline results block at the bottom of `main()`:

```python
# OLD (remove this entire block):
    print("\n--- Results ---")
    passed_count = 0
    for item_result in result.item_results:
        evals = item_result.evaluations or []
        passed = all(ev.value == 1.0 for ev in evals)
        elapsed = item_result.output.get("elapsed", 0) if item_result.output else 0
        for ev in evals:
            icon = "✓" if ev.value == 1.0 else "✗"
            print(f"  {icon} {ev.name}: {ev.comment}")
        print(f"  {'PASS' if passed else 'FAIL'}  ({elapsed:.1f}s)")
        if passed:
            passed_count += 1

    total = len(result.item_results)
    print(f"\n{passed_count}/{total} passed")

    if result.dataset_run_url:
        print(f"View: {result.dataset_run_url}")
    else:
        print(f"View: {LANGFUSE_HOST}")

# NEW (one line):
    _print_results("sanity", result)
```

- [ ] **Step 3: Verify the module imports cleanly**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/python -c "import evals.run; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Run existing tests to confirm no regression**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/ -v --ignore=tests/test_evals.py 2>&1 | tail -10
```

Expected: all existing tests pass.

- [ ] **Step 5: Commit**

```bash
git add evals/run.py
git commit -m "refactor(evals): extract _print_results, add build-skill constants"
```

---

### Task 3: `build_skill_task` function + tests

**Files:**
- Modify: `evals/run.py`
- Modify: `tests/test_evals.py`

**Interfaces:**
- Consumes: `BUILD_TIMEOUT`, `COMMANDS_PATH`, `SKILLS_DIR`, `tools.EXECUTORS`, `run_turn`, `History`, `_final_text`, `_tool_calls`, `_turn_count`
- Produces: `build_skill_task(*, item, **kwargs) -> dict` with keys `text`, `tool_calls`, `turn_count`, `elapsed`, `timed_out`, `files_written`

Note: `build_skill_task` is defined inside `main()` (same pattern as the existing `task`/`sanity_task`). The tests below test it indirectly by calling a standalone version extracted for testability. Define a module-level `_build_skill_task_fn` that contains the logic, which `build_skill_task` wraps.

Actually, for simplicity: test `build_skill_task` behavior via mocks on a standalone helper. The cleanest approach is to define the logic in a module-level async function `_run_build_skill(history, config, item_input)` that `build_skill_task` calls, and test `_run_build_skill` directly.

Instead — since testing the full `build_skill_task` requires a real or mocked Langfuse `item` — we'll test its key behaviors via two targeted tests: one for timeout and one for cleanup.

- [ ] **Step 1: Add tests to `tests/test_evals.py`**

Append to `tests/test_evals.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import os


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
```

- [ ] **Step 2: Run new tests to verify they fail**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/test_evals.py::test_build_skill_task_sets_timed_out_on_timeout tests/test_evals.py::test_build_skill_task_cleanup_deletes_written_skill_files -v 2>&1 | tail -15
```

Expected: PASS — these tests inline the `build_skill_task` logic rather than importing it, so they pass as soon as `evals.run` is importable (Task 2). They validate the timeout and cleanup pattern before it is wired into `main()`.

- [ ] **Step 3: Add `build_skill_task` inside `main()` in `evals/run.py`**

After the `_print_results("sanity", result)` call in `main()`, add:

```python
    # ── build-skill experiment ─────────────────────────────────────────────────
    try:
        lf.create_dataset(name=BUILD_DATASET, description="Jarvis Code build-skill evals")
    except Exception:
        pass

    lf.create_dataset_item(
        dataset_name=BUILD_DATASET,
        input={"prompt": BUILD_PROMPT},
        expected_output={"file": "jarvis/skills/remind.py", "max_turns": 25},
        id="build-skill-v1",
    )

    build_ds = lf.get_dataset(BUILD_DATASET)
    print(f"\nDataset: {BUILD_DATASET} ({len(build_ds.items)} items)")

    async def build_skill_task(*, item, **kwargs):
        history = History()
        history.append_user(item.input["prompt"])

        files_written: list[str] = []
        original_commands = COMMANDS_PATH.read_text()
        original_write = tools.EXECUTORS.get("write_file")

        async def tracking_write(**kw):
            files_written.append(kw.get("path", ""))
            return await original_write(**kw)

        timed_out = False
        elapsed = 0.0
        start = time.monotonic()
        print(f"[running] {item.input['prompt']!r}")

        try:
            with patch.dict(tools.EXECUTORS, {"write_file": tracking_write}):
                await asyncio.wait_for(run_turn(history, config), timeout=BUILD_TIMEOUT)
        except asyncio.TimeoutError:
            timed_out = True
        finally:
            elapsed = time.monotonic() - start
            COMMANDS_PATH.write_text(original_commands)
            for p in files_written:
                fp = Path(os.path.abspath(p))
                if fp.exists() and str(fp).startswith(str(SKILLS_DIR)):
                    fp.unlink()

        return {
            "text": _final_text(history),
            "tool_calls": _tool_calls(history),
            "turn_count": _turn_count(history),
            "elapsed": elapsed,
            "timed_out": timed_out,
            "files_written": files_written,
        }
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/test_evals.py -v 2>&1 | tail -15
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add evals/run.py tests/test_evals.py
git commit -m "feat(evals): add build_skill_task with timeout + write tracker + cleanup"
```

---

### Task 4: Three evaluators + tests

**Files:**
- Modify: `evals/run.py`
- Modify: `tests/test_evals.py`

**Interfaces:**
- Consumes: `build_skill_task` output shape (`timed_out`, `turn_count`, `tool_calls`, `files_written`, `elapsed`)
- Produces: `eval_completed_in_time`, `eval_turns_reasonable`, `eval_file_created` — each takes `(*, output, expected_output=None, **kwargs)` and returns `Evaluation`

- [ ] **Step 1: Add evaluator tests to `tests/test_evals.py`**

Append to `tests/test_evals.py`:

```python
from langfuse.experiment import Evaluation


def _build_output(timed_out=False, turn_count=5, tool_calls=None, files_written=None, elapsed=10.0):
    return {
        "text": "done",
        "tool_calls": tool_calls or ["read_file", "write_file"],
        "turn_count": turn_count,
        "elapsed": elapsed,
        "timed_out": timed_out,
        "files_written": files_written or [],
    }


# ── eval_completed_in_time ────────────────────────────────────────────────────

def test_eval_completed_in_time_pass():
    from evals.run import eval_completed_in_time
    ev = eval_completed_in_time(output=_build_output(timed_out=False))
    assert ev.value == 1.0
    assert "completed" in ev.comment


def test_eval_completed_in_time_fail():
    from evals.run import eval_completed_in_time
    ev = eval_completed_in_time(output=_build_output(timed_out=True))
    assert ev.value == 0.0
    assert "TIMED OUT" in ev.comment


# ── eval_turns_reasonable ─────────────────────────────────────────────────────

def test_eval_turns_reasonable_pass():
    from evals.run import eval_turns_reasonable
    ev = eval_turns_reasonable(
        output=_build_output(turn_count=10),
        expected_output={"max_turns": 25},
    )
    assert ev.value == 1.0
    assert "10 turns" in ev.comment


def test_eval_turns_reasonable_fail_over_budget():
    from evals.run import eval_turns_reasonable
    ev = eval_turns_reasonable(
        output=_build_output(turn_count=30),
        expected_output={"max_turns": 25},
    )
    assert ev.value == 0.0
    assert "exceeded" in ev.comment


def test_eval_turns_reasonable_fail_on_timeout():
    from evals.run import eval_turns_reasonable
    # Even with low turn count, timed_out=True must fail this evaluator
    ev = eval_turns_reasonable(
        output=_build_output(timed_out=True, turn_count=3),
        expected_output={"max_turns": 25},
    )
    assert ev.value == 0.0


def test_eval_turns_reasonable_comment_includes_tool_calls():
    from evals.run import eval_turns_reasonable
    ev = eval_turns_reasonable(
        output=_build_output(turn_count=5, tool_calls=["read_file", "bash", "write_file"]),
        expected_output={"max_turns": 25},
    )
    assert "read_file" in ev.comment


# ── eval_file_created ─────────────────────────────────────────────────────────

def test_eval_file_created_pass():
    from evals.run import eval_file_created
    ev = eval_file_created(
        output=_build_output(files_written=["jarvis/skills/remind.py"]),
        expected_output={"file": "jarvis/skills/remind.py"},
    )
    assert ev.value == 1.0
    assert "wrote" in ev.comment


def test_eval_file_created_pass_absolute_path():
    from evals.run import eval_file_created
    ev = eval_file_created(
        output=_build_output(files_written=["/Users/x/jarvis-code/jarvis/skills/remind.py"]),
        expected_output={"file": "jarvis/skills/remind.py"},
    )
    assert ev.value == 1.0


def test_eval_file_created_fail_empty():
    from evals.run import eval_file_created
    ev = eval_file_created(
        output=_build_output(files_written=[]),
        expected_output={"file": "jarvis/skills/remind.py"},
    )
    assert ev.value == 0.0
    assert "did NOT write" in ev.comment


def test_eval_file_created_fail_wrong_file():
    from evals.run import eval_file_created
    ev = eval_file_created(
        output=_build_output(files_written=["jarvis/skills/other.py"]),
        expected_output={"file": "jarvis/skills/remind.py"},
    )
    assert ev.value == 0.0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/test_evals.py -k "eval_completed or eval_turns or eval_file" -v 2>&1 | tail -20
```

Expected: `ImportError` — `eval_completed_in_time` etc. not defined yet.

- [ ] **Step 3: Add evaluators to `evals/run.py`**

Add these three functions at module level (outside `main()`, after `_print_results`):

```python
def eval_completed_in_time(*, output, **kwargs):
    ok = not output["timed_out"]
    return Evaluation(
        name="completed_in_time",
        value=1.0 if ok else 0.0,
        comment=f"{'completed' if ok else f'TIMED OUT after {BUILD_TIMEOUT}s'} ({output['elapsed']:.1f}s)",
    )


def eval_turns_reasonable(*, output, expected_output=None, **kwargs):
    max_t = (expected_output or {}).get("max_turns", 25)
    n = output["turn_count"]
    ok = not output["timed_out"] and n <= max_t
    return Evaluation(
        name="turns_reasonable",
        value=1.0 if ok else 0.0,
        comment=f"{n} turns ({'ok' if ok else f'exceeded {max_t}'}), tools: {output['tool_calls']}",
    )


def eval_file_created(*, output, expected_output=None, **kwargs):
    target = (expected_output or {}).get("file", "jarvis/skills/remind.py")
    created = any(target in f for f in output["files_written"])
    return Evaluation(
        name="file_created",
        value=1.0 if created else 0.0,
        comment=f"{'wrote' if created else 'did NOT write'} {target} (wrote: {output['files_written']})",
    )
```

- [ ] **Step 4: Run all tests**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/test_evals.py -v 2>&1 | tail -25
```

Expected: all tests PASS.

- [ ] **Step 5: Commit**

```bash
git add evals/run.py tests/test_evals.py
git commit -m "feat(evals): add build-skill evaluators with tests"
```

---

### Task 5: Wire second experiment into `main()` and run end-to-end

**Files:**
- Modify: `evals/run.py`

**Interfaces:**
- Consumes: `build_skill_task` (defined in Task 3), `eval_completed_in_time`, `eval_turns_reasonable`, `eval_file_created` (defined in Task 4)

- [ ] **Step 1: Add `lf.run_experiment` call for build-skill**

At the end of `main()`, after `build_skill_task` definition, add:

```python
    build_result = lf.run_experiment(
        name="jarvis-build-skill",
        data=build_ds.items,
        task=build_skill_task,
        evaluators=[eval_completed_in_time, eval_turns_reasonable, eval_file_created],
        max_concurrency=1,
        metadata={"model": config.model},
    )
    _print_results("build-skill", build_result)

    lf.flush()
```

Remove or replace the existing `lf.flush()` call that was at the bottom — there should only be one `lf.flush()`, at the very end of `main()`.

- [ ] **Step 2: Verify module imports cleanly**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/python -c "import evals.run; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Run all unit tests**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/pytest tests/ -v 2>&1 | tail -15
```

Expected: all tests PASS.

- [ ] **Step 4: Run the eval end-to-end**

```bash
cd /Users/adminaccount/Documents/jarvis-code && .venv/bin/python -m evals.run
```

Expected output will be one of:
- **Hang at 120s then:** `✗ completed_in_time: TIMED OUT after 120s` → confirms the bug; the `turns_reasonable` comment shows how many turns occurred before timeout
- **Completes but many turns:** `✗ turns_reasonable: 32 turns (exceeded 25), tools: [...]` → reveals runaway loop pattern
- **All pass:** eval unexpectedly succeeds (unlikely for the build-skill task but possible)

After the run, verify the repo is clean:

```bash
cd /Users/adminaccount/Documents/jarvis-code && git status
```

Expected: clean working tree — no `jarvis/skills/remind.py` left behind, `jarvis/commands.py` unchanged.

- [ ] **Step 5: Commit**

```bash
git add evals/run.py
git commit -m "feat(evals): wire build-skill experiment into main() — eval-first hang diagnosis"
```
