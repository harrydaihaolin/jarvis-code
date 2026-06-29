# Eval: Build-Skill Hang Diagnosis

**Date:** 2026-06-28
**Status:** Approved

## Problem

When a user asks jarvis to build a new skill (e.g. "build a new skill called /btw, structured exactly like the current one"), the CLI hangs indefinitely. Root cause: `run_turn` in `jarvis/query.py` is a bare `while True` with no turn cap or timeout. A complex agentic task (read btw.py, read commands.py, write new file, re-read to verify, ...) can make 15–25+ tool calls with nothing to stop it.

The user also wants visual progress at each step so they can see the agent is working rather than frozen.

## Approach

Eval-first. Build the eval to surface how many turns the task takes and whether it terminates. The eval results inform the right `max_turns` value and where to add progress prints to `run_turn`. The eval becomes the regression guard for the fix.

## Architecture

All changes in `evals/run.py`. No new files.

Add one new dataset item (`build-skill-v1`) to the existing `jarvis-sanity` Langfuse dataset alongside `read-file-sanity-v1`.

### Dataset Item

```
input:  {"prompt": "Build a new skill called /remind, structured exactly like /btw. Create jarvis/skills/remind.py and register /remind in jarvis/commands.py."}
expected_output: {"file": "jarvis/skills/remind.py", "max_turns": 25}
id: "build-skill-v1"
```

### Task Function

Three responsibilities:

1. **Timeout wrapper** — `asyncio.wait_for(run_turn(...), timeout=120)` prevents the eval runner from hanging the way the CLI does. Sets `timed_out=True` on `TimeoutError`.

2. **Write-file tracker** — patches `tools.EXECUTORS["write_file"]` with a thin async wrapper that appends every `path` argument to a `files_written` list before delegating to the real executor. Lets evaluators check whether the target skill file appeared.

3. **State cleanup in `finally`** — before the run, saves `jarvis/commands.py` content and restores it after; deletes any files written under `jarvis/skills/` so the repo is clean for re-runs.

### Turn Count

Derived post-run from history: count messages where `role == "user"` and content is a list containing `tool_result` blocks. One such message = one completed tool-use cycle. No changes to `run_turn`.

### Task Output Shape

```python
{
    "text": str,           # final assistant text
    "tool_calls": list[str],  # tool names in call order
    "turn_count": int,     # tool-use cycles completed before stop/timeout
    "elapsed": float,      # wall-clock seconds
    "timed_out": bool,
    "files_written": list[str],
}
```

## Evaluators

Three new evaluators, applied only to `build-skill-v1`:

| Evaluator | Pass condition | Comment surfaced |
|---|---|---|
| `completed_in_time` | `not timed_out` | Elapsed time, or "TIMED OUT after 120s" |
| `turns_reasonable` | `turn_count ≤ expected_output["max_turns"]` (25) | Exact count + full tool call sequence in order |
| `file_created` | target file in `files_written` | Which files were actually written |

`turns_reasonable` is the diagnostic core: its comment prints the full tool call sequence, revealing exactly where the agent loops or stalls.

## What the Eval Reveals → Fix

| Eval result | Root cause | Fix |
|---|---|---|
| `completed_in_time` fails | `run_turn` never exits | Add `max_turns: int = 40` default; break/raise at limit |
| `turns_reasonable` fails, count > 25 | Runaway tool loop | Same fix; use observed count to pick threshold |
| `turns_reasonable` comment shows repeated `read_file` calls | Agent re-verifying in a loop | Improve system prompt or add a "done" signal |
| `file_created` fails | Agent wrote to wrong path | Fix prompt or path handling |

After the eval run, add to `run_turn`:
- `max_turns: int = 40` parameter
- Per-step print: `[Turn N/max_turns] tool_name running...` replacing the current bare `[tool_name] running...`

## Testing

No new unit tests for the eval script itself. The existing `test_query.py` tests cover `run_turn` behavior. After the fix is applied, a new test for the `max_turns` guard should be added to `tests/test_query.py`.
