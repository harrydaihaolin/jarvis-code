# Jarvis Code

Personal AI coding assistant CLI powered by Claude.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
export ANTHROPIC_API_KEY=your_key_here
```

## Run

```bash
jarvis
jarvis --model claude-haiku-4-5-20251001
```

## Commands

| Command | Action |
|---|---|
| `/help` | List available commands |
| `/clear` | Reset conversation history |
| `/exit` | Quit |
