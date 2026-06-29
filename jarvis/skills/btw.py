"""
/btw skill — asynchronously spawn a sub-agent to answer side questions
while the main conversation thread keeps running uninterrupted.

Usage:
    /btw <question>

Examples:
    /btw what does os.path.join actually return when the path starts with /?
    /btw is asyncio.create_task safe to call from a sync context?

The sub-agent runs in a fire-and-forget asyncio Task with its own isolated
History.  Its streamed reply is printed live with a "[btw]" prefix so it is
visually distinct from the main thread output.  Errors in the sub-agent never
propagate to the main loop.
"""

from __future__ import annotations

import asyncio
import sys
from typing import TYPE_CHECKING

from ..history import History
from .. import query

if TYPE_CHECKING:
    from ..config import Config

# ── cosmetics ────────────────────────────────────────────────────────────────
_PREFIX = "\033[36m[btw]\033[0m "   # cyan prefix in colour-capable terminals
_SEPARATOR = "\033[36m" + "─" * 60 + "\033[0m"

BTW_SYSTEM_ADDENDUM = """\

You are operating as a lightweight side-channel sub-agent.  The user has asked
a quick aside ("btw") while their main conversation is ongoing.  Answer the
question concisely and clearly.  Do not reference the main conversation — you
do not have access to it.  Use tools only if genuinely necessary to give an
accurate answer; otherwise prefer a direct textual response.
"""


# ── public entry point ───────────────────────────────────────────────────────

def spawn(question: str, config: "Config") -> asyncio.Task:
    """
    Fire-and-forget: create an asyncio Task that answers *question* in the
    background and prints the result prefixed with [btw].

    Returns the Task so callers can optionally await or cancel it.
    """
    task = asyncio.ensure_future(_run(question, config))
    task.add_done_callback(_on_done)
    return task


# ── internals ────────────────────────────────────────────────────────────────

async def _run(question: str, config: "Config") -> None:
    """Full sub-agent turn: stream the answer, print it with [btw] prefix."""
    import anthropic
    from .. import persona, tools

    history = History()
    history.append_user(question)

    system = persona.SYSTEM_PROMPT + BTW_SYSTEM_ADDENDUM

    client = anthropic.AsyncAnthropic(api_key=config.api_key)

    # Print a header so the user knows the sub-agent has started
    print(f"\n{_SEPARATOR}", flush=True)
    print(f"{_PREFIX}answering: {question}", flush=True)

    while True:
        async with client.messages.stream(
            model=config.model,
            system=system,
            tools=tools.ALL,
            messages=history.messages,
            max_tokens=2048,          # sub-agent answers are intentionally capped
        ) as stream:
            # Stream tokens live with the [btw] prefix on the first chunk
            first_chunk = True
            async for text in stream.text_stream:
                if first_chunk:
                    print(_PREFIX, end="", flush=True)
                    first_chunk = False
                # Indent continuation lines so every line carries the prefix
                print(text.replace("\n", f"\n{_PREFIX}"), end="", flush=True)

            message = await stream.get_final_message()

        print()   # newline after streamed text
        history.append_assistant_message(message)

        if message.stop_reason != "tool_use":
            break

        # Handle any tool calls the sub-agent decides to make
        tool_results = []
        for block in message.content:
            if block.type != "tool_use":
                continue
            executor = tools.EXECUTORS.get(block.name)
            print(f"\n{_PREFIX}[{block.name}] running...", flush=True)
            try:
                result = await executor(**block.input) if executor else f"Error: unknown tool '{block.name}'"
            except Exception as exc:
                result = f"Error running {block.name}: {exc}"
            tool_results.append({"tool_use_id": block.id, "content": result})

        if not tool_results:
            break
        history.append_tool_results(tool_results)

    print(f"{_SEPARATOR}\n", flush=True)


def _on_done(task: asyncio.Task) -> None:
    """Swallow CancelledError; surface unexpected exceptions without crashing."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        print(f"\n{_PREFIX}\033[31merror:\033[0m {exc}", file=sys.stderr, flush=True)
