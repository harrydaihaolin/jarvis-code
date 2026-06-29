# Jarvis Code

Personal AI coding assistant CLI powered by Claude.

## Install

```bash
uv sync --extra dev
export ANTHROPIC_API_KEY=your_key_here
```

## Test

```bash
uv run pytest
```

## Run

```bash
uv run jarvis
uv run jarvis --model claude-haiku-4-5-20251001
```

## Upgrade

If you installed Jarvis as a global tool (`uv tool install .`), upgrade to the
latest version from the repo with:

```bash
jarvis upgrade
```

## Commands

| Command | Action |
|---|---|
| `/help` | List available commands |
| `/clear` | Reset conversation history |
| `/exit` | Quit |
