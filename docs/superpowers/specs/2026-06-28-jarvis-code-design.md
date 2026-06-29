# Jarvis Code v1 — Design Spec

**Date:** 2026-06-28
**Status:** Approved

---

## What It Is

Jarvis Code is a personal desktop coding assistant CLI. It runs in the terminal, talks to the Anthropic API, can read/write files and run shell commands, and is architected so the Anthropic Agents SDK can be dropped in later without restructuring.

---

## Stack

| Layer | Choice |
|---|---|
| Language | Python 3.12+ |
| Async | `asyncio` (native) |
| LLM client | `anthropic` Python SDK (async) |
| Terminal input | `asyncio` + `sys.stdin` in executor |
| Config | `ANTHROPIC_API_KEY` env var only — fail fast if missing |
| Default model | `claude-sonnet-4-6` (overridable via `--model` flag) |

---

## Project Structure

```
jarvis-code/
├── jarvis/
│   ├── main.py          # Entry point: asyncio.run(main())
│   ├── query.py         # Anthropic streaming + tool-call loop
│   ├── history.py       # Conversation state (list[MessageParam])
│   ├── config.py        # Reads ANTHROPIC_API_KEY, model, flags
│   ├── commands.py      # Slash command router
│   ├── persona.py       # System prompt / Jarvis identity
│   └── tools/
│       ├── __init__.py  # Tool registry — list[ToolParam] exported here
│       ├── read.py      # Read file from disk
│       ├── write.py     # Write / create file
│       └── bash.py      # Execute shell command (async subprocess)
├── pyproject.toml
└── README.md
```

---

## Data Flow

```
asyncio.run(main())
        ↓
  async readline input
        ↓
  slash command? → commands.py handles locally (no API call)
        ↓
  history.append({"role": "user", "content": input})
        ↓
  query.py: AsyncAnthropic.messages.stream(
      model=config.model,
      system=persona.SYSTEM_PROMPT,
      tools=tools.ALL,
      messages=history.messages
  )
        ↓
  stream tokens → print to stdout as they arrive
        ↓
  stop_reason == "tool_use"?
  ├── yes → dispatch to tools/[read|write|bash].py (async)
  │          history.append(tool result)
  │          loop back to query
  └── no  → turn complete, await next input
```

---

## Components

### `main.py`
Entry point. Reads `--model` CLI flag. Starts the async REPL loop: prompt → route → repeat.

### `query.py`
Pure async function: takes `(history, tools, config)` → streams response → returns completed message. No I/O side effects. This is the **agent SDK seam** — can be replaced with an agents SDK step function without touching anything else.

### `history.py`
Holds `list[MessageParam]`. Exposes `append(role, content)` and `clear()`. `/clear` command resets it.

### `config.py`
Reads `ANTHROPIC_API_KEY` from environment. Raises `RuntimeError` immediately if missing. Holds model name and any other runtime settings.

### `persona.py`
Single constant: `SYSTEM_PROMPT`. Defines Jarvis's identity, coding focus, and behavior defaults.

### `commands.py`
Routes `/command` strings before they reach the LLM. v1 commands:
- `/help` — print available commands
- `/clear` — reset conversation history
- `/exit` — quit

### `tools/__init__.py`
Exports `ALL: list[ToolParam]` — the tool definitions sent to the API on every request.

### `tools/read.py`
Reads a file path from disk. Returns content as string. No permission gate.

### `tools/write.py`
Writes content to a file path. Creates parent dirs if needed. No permission gate.

### `tools/bash.py`
Runs a shell command via `asyncio.create_subprocess_shell`. Returns stdout + stderr. No permission gate.

---

## Permission Model

Trust-by-default. No HITL approval prompts in v1. The user (sole operator) accepts full responsibility for tool execution. Optimized for harness/agentic engineering speed.

---

## Agent SDK Extension Plan

`query.py` is intentionally isolated as a pure function with no side effects. When the Anthropic Agents SDK is ready to integrate:

- `query.py` either becomes the agent's `step()` implementation
- or is replaced entirely — history and tools format (native `anthropic` SDK types) are compatible with the agents SDK out of the box
- Tools in `tools/` can be registered directly with the agents SDK without modification

---

## Out of Scope for v1

- FastAPI / HTTP server layer
- Web UI or IDE extension
- Permission / approval prompts
- Cost tracking
- Syntax highlighting
- Multi-agent orchestration
- Config file (`~/.jarvis`)
