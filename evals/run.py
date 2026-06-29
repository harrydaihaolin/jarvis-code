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

LANGFUSE_HOST = os.environ.get("LANGFUSE_BASE_URL", "http://localhost:3000")
DATASET_NAME = "jarvis-sanity"
EVAL_FILE = "/tmp/jarvis_eval.txt"
EVAL_CONTENT = "jarvis-eval-42"
PROMPT = f"Read {EVAL_FILE} and tell me what's in it"

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


def _tool_calls(history: History) -> list[str]:
    names = []
    for msg in history.messages:
        if msg["role"] == "assistant":
            for block in msg["content"]:
                if block.get("type") == "tool_use":
                    names.append(block["name"])
    return names


def _final_text(history: History) -> str:
    for msg in reversed(history.messages):
        if msg["role"] == "assistant":
            for block in msg["content"]:
                if block.get("type") == "text":
                    return block["text"]
    return ""


def _turn_count(history: History) -> int:
    """Count completed tool-use cycles (user messages that contain tool_result blocks)."""
    return sum(
        1
        for msg in history.messages
        if msg["role"] == "user"
        and isinstance(msg["content"], list)
        and any(b.get("type") == "tool_result" for b in msg["content"])
    )


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


async def main() -> None:
    lf = Langfuse(
        public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
        secret_key=os.environ["LANGFUSE_SECRET_KEY"],
        host=LANGFUSE_HOST,
    )
    config = load_config()

    print("=== Jarvis Code Eval ===")

    # Upsert dataset (create is idempotent if name already exists)
    try:
        lf.create_dataset(name=DATASET_NAME, description="Jarvis Code sanity checks")
    except Exception:
        pass

    # Upsert item — stable id prevents duplicates across runs
    lf.create_dataset_item(
        dataset_name=DATASET_NAME,
        input={"prompt": PROMPT},
        expected_output={"contains": EVAL_CONTENT},
        id="read-file-sanity-v1",
    )

    dataset = lf.get_dataset(DATASET_NAME)
    print(f"Dataset: {DATASET_NAME} ({len(dataset.items)} items)\n")

    async def task(*, item, **kwargs):
        with open(EVAL_FILE, "w") as f:
            f.write(EVAL_CONTENT)

        history = History()
        history.append_user(item.input["prompt"])

        start = time.monotonic()
        print(f"[running] {item.input['prompt']!r}")
        await run_turn(history, config)
        elapsed = time.monotonic() - start

        return {
            "text": _final_text(history),
            "tool_calls": _tool_calls(history),
            "elapsed": elapsed,
        }

    def eval_tool_called(*, input, output, expected_output=None, **kwargs):
        called = "read_file" in output["tool_calls"]
        return Evaluation(
            name="tool_called",
            value=1.0 if called else 0.0,
            comment=f"read_file {'called' if called else 'NOT called'} (saw: {output['tool_calls']})",
        )

    def eval_content_present(*, input, output, expected_output=None, **kwargs):
        target = (expected_output or {}).get("contains", EVAL_CONTENT)
        present = target in output["text"]
        return Evaluation(
            name="content_present",
            value=1.0 if present else 0.0,
            comment=f"'{target}' {'found' if present else 'NOT found'} in response",
        )

    result = lf.run_experiment(
        name="jarvis-sanity",
        data=dataset.items,
        task=task,
        evaluators=[eval_tool_called, eval_content_present],
        max_concurrency=1,
        metadata={"model": config.model},
    )

    _print_results("sanity", result)

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
        original_write = tools.EXECUTORS["write_file"]

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


if __name__ == "__main__":
    asyncio.run(main())
