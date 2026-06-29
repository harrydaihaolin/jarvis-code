# Jarvis Code v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python async CLI coding assistant that streams responses from the Anthropic API, executes file and shell tools in a loop, and is structured so the Anthropic Agents SDK can replace the query layer later.

**Architecture:** A thin async REPL (`main.py`) routes user input to either a local slash-command handler (`commands.py`) or the query engine (`query.py`). The query engine streams from the Anthropic API, detects `tool_use` stop reasons, dispatches to async tool executors, appends results to conversation history, and loops until the model returns a natural text response.

**Tech Stack:** Python 3.12+, `asyncio`, `anthropic>=0.39.0` (async client), `pytest`, `pytest-asyncio`

## Global Constraints

- Python 3.12+ required — use `match` statements and `type X = Y` aliases freely
- `anthropic>=0.39.0` — use `AsyncAnthropic`, `client.messages.stream()`
- No permission gates on any tool — trust-by-default
- Config is `ANTHROPIC_API_KEY` env var only — `RuntimeError` immediately if missing
- Default model: `claude-sonnet-4-6`
- All tool executor functions are `async def execute(**kwargs) -> str`
- Repo root: `/Users/adminaccount/Documents/jarvis-code/`
- Run all commands from repo root

---

### Task 1: Project Scaffold + GitHub Remote

**Files:**
- Create: `pyproject.toml`
- Create: `jarvis/__init__.py`
- Create: `jarvis/tools/__init__.py` (empty placeholder)
- Create: `tests/__init__.py`
- Create: `tests/tools/__init__.py`
- Create: `.gitignore`
- Create: `README.md`

**Interfaces:**
- Produces: `jarvis` installable package; `jarvis` CLI entry point via `pyproject.toml`

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "jarvis-code"
version = "0.1.0"
description = "Jarvis Code — personal AI coding assistant CLI"
requires-python = ">=3.12"
dependencies = [
    "anthropic>=0.39.0",
]

[project.scripts]
jarvis = "jarvis.main:run"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.py[cod]
*.pyo
.venv/
venv/
dist/
build/
*.egg-info/
.pytest_cache/
.env
.DS_Store
```

- [ ] **Step 3: Write `README.md`**

```markdown
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
```

- [ ] **Step 4: Create package init files**

`jarvis/__init__.py` — empty file.

`jarvis/tools/__init__.py` — empty file (will be filled in Task 6).

`tests/__init__.py` — empty file.

`tests/tools/__init__.py` — empty file.

- [ ] **Step 5: Install dependencies**

```bash
python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
```

Expected: `Successfully installed jarvis-code-0.1.0 ...`

- [ ] **Step 6: Create GitHub remote and push**

```bash
gh repo create harrydaihaolin/jarvis-code --public --source=. --remote=origin --push
```

Expected: `✓ Created repository harrydaihaolin/jarvis-code on GitHub`

- [ ] **Step 7: Commit scaffold**

```bash
git add pyproject.toml .gitignore README.md jarvis/__init__.py jarvis/tools/__init__.py tests/__init__.py tests/tools/__init__.py
git commit -m "chore: project scaffold, pyproject.toml, package structure"
git push
```

---

### Task 2: Config

**Files:**
- Create: `jarvis/config.py`
- Create: `tests/test_config.py`

**Interfaces:**
- Produces: `Config` dataclass with fields `api_key: str`, `model: str`
- Produces: `load_config(model: str = "claude-sonnet-4-6") -> Config`

- [ ] **Step 1: Write failing tests**

`tests/test_config.py`:
```python
import os
import pytest
from jarvis.config import load_config, Config


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        load_config()


def test_load_config_returns_config(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    config = load_config()
    assert isinstance(config, Config)
    assert config.api_key == "sk-test-key"
    assert config.model == "claude-sonnet-4-6"


def test_load_config_custom_model(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")
    config = load_config(model="claude-haiku-4-5-20251001")
    assert config.model == "claude-haiku-4-5-20251001"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ERROR ... ModuleNotFoundError: No module named 'jarvis.config'`

- [ ] **Step 3: Write `jarvis/config.py`**

```python
import os
from dataclasses import dataclass


@dataclass
class Config:
    api_key: str
    model: str


def load_config(model: str = "claude-sonnet-4-6") -> Config:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY environment variable is not set. "
            "Export it before running Jarvis: export ANTHROPIC_API_KEY=your_key"
        )
    return Config(api_key=api_key, model=model)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected:
```
PASSED tests/test_config.py::test_missing_api_key_raises
PASSED tests/test_config.py::test_load_config_returns_config
PASSED tests/test_config.py::test_load_config_custom_model
3 passed
```

- [ ] **Step 5: Commit**

```bash
git add jarvis/config.py tests/test_config.py
git commit -m "feat: config — load ANTHROPIC_API_KEY from env, fail fast if missing"
git push
```

---

### Task 3: Persona + History

**Files:**
- Create: `jarvis/persona.py`
- Create: `jarvis/history.py`
- Create: `tests/test_history.py`

**Interfaces:**
- Produces: `SYSTEM_PROMPT: str` from `jarvis.persona`
- Produces: `History` class with methods:
  - `append_user(content: str) -> None`
  - `append_assistant_message(message) -> None` — accepts `anthropic.types.Message`
  - `append_tool_results(results: list[dict]) -> None` — each dict: `{"tool_use_id": str, "content": str}`
  - `clear() -> None`
  - `messages: list[dict]` property

- [ ] **Step 1: Write failing tests**

`tests/test_history.py`:
```python
import pytest
from unittest.mock import MagicMock
from jarvis.history import History


def test_append_user_adds_user_message():
    h = History()
    h.append_user("hello")
    assert h.messages == [{"role": "user", "content": "hello"}]


def test_clear_empties_history():
    h = History()
    h.append_user("hello")
    h.clear()
    assert h.messages == []


def test_messages_returns_copy():
    h = History()
    h.append_user("hello")
    msgs = h.messages
    msgs.append({"role": "user", "content": "injected"})
    assert len(h.messages) == 1


def test_append_tool_results_adds_user_message_with_tool_results():
    h = History()
    results = [
        {"tool_use_id": "toolu_001", "content": "file contents here"},
        {"tool_use_id": "toolu_002", "content": "command output"},
    ]
    h.append_tool_results(results)
    assert h.messages == [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_001", "content": "file contents here"},
                {"type": "tool_result", "tool_use_id": "toolu_002", "content": "command output"},
            ],
        }
    ]


def test_append_assistant_message_text_only():
    h = History()
    message = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello, I can help!"
    message.content = [text_block]
    h.append_assistant_message(message)
    assert h.messages == [
        {"role": "assistant", "content": [{"type": "text", "text": "Hello, I can help!"}]}
    ]


def test_append_assistant_message_with_tool_use():
    h = History()
    message = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_001"
    tool_block.name = "read_file"
    tool_block.input = {"path": "/tmp/foo.py"}
    message.content = [tool_block]
    h.append_assistant_message(message)
    assert h.messages == [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_001",
                    "name": "read_file",
                    "input": {"path": "/tmp/foo.py"},
                }
            ],
        }
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_history.py -v
```

Expected: `ERROR ... ModuleNotFoundError: No module named 'jarvis.history'`

- [ ] **Step 3: Write `jarvis/persona.py`**

```python
SYSTEM_PROMPT = """\
You are Jarvis, a personal desktop coding assistant. You help with coding tasks: \
reading and editing files, running shell commands, explaining code, debugging, and more.

You have access to tools: read_file, write_file, and bash. Use them freely — \
the user trusts you to act without asking permission first. When you need to \
look at a file or run a command to answer a question, just do it.

Be concise and direct. Prefer actions over explanations when the task is clear.\
"""
```

- [ ] **Step 4: Write `jarvis/history.py`**

```python
class History:
    def __init__(self) -> None:
        self._messages: list[dict] = []

    @property
    def messages(self) -> list[dict]:
        return list(self._messages)

    def append_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def append_assistant_message(self, message) -> None:
        content = []
        for block in message.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input),
                })
        self._messages.append({"role": "assistant", "content": content})

    def append_tool_results(self, results: list[dict]) -> None:
        content = [
            {
                "type": "tool_result",
                "tool_use_id": r["tool_use_id"],
                "content": r["content"],
            }
            for r in results
        ]
        self._messages.append({"role": "user", "content": content})

    def clear(self) -> None:
        self._messages.clear()
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_history.py -v
```

Expected:
```
PASSED tests/test_history.py::test_append_user_adds_user_message
PASSED tests/test_history.py::test_clear_empties_history
PASSED tests/test_history.py::test_messages_returns_copy
PASSED tests/test_history.py::test_append_tool_results_adds_user_message_with_tool_results
PASSED tests/test_history.py::test_append_assistant_message_text_only
PASSED tests/test_history.py::test_append_assistant_message_with_tool_use
6 passed
```

- [ ] **Step 6: Commit**

```bash
git add jarvis/persona.py jarvis/history.py tests/test_history.py
git commit -m "feat: persona system prompt and conversation history"
git push
```

---

### Task 4: File Tools (read + write)

**Files:**
- Create: `jarvis/tools/read.py`
- Create: `jarvis/tools/write.py`
- Create: `tests/tools/test_file_tools.py`

**Interfaces:**
- Produces: `jarvis.tools.read.execute(path: str) -> str`
- Produces: `jarvis.tools.read.DEFINITION: dict`
- Produces: `jarvis.tools.write.execute(path: str, content: str) -> str`
- Produces: `jarvis.tools.write.DEFINITION: dict`

- [ ] **Step 1: Write failing tests**

`tests/tools/test_file_tools.py`:
```python
import os
import pytest
from jarvis.tools import read, write


@pytest.mark.asyncio
async def test_read_existing_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = await read.execute(path=str(f))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_read_missing_file():
    result = await read.execute(path="/nonexistent/path/file.txt")
    assert "not found" in result.lower() or "error" in result.lower()


def test_read_definition_has_required_fields():
    d = read.DEFINITION
    assert d["name"] == "read_file"
    assert "path" in d["input_schema"]["properties"]
    assert "path" in d["input_schema"]["required"]


@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    path = str(tmp_path / "output.txt")
    result = await write.execute(path=path, content="written content")
    assert os.path.exists(path)
    assert open(path).read() == "written content"
    assert "written" in result.lower() or str(path) in result


@pytest.mark.asyncio
async def test_write_creates_parent_directories(tmp_path):
    path = str(tmp_path / "nested" / "deep" / "file.txt")
    await write.execute(path=path, content="deep file")
    assert os.path.exists(path)


@pytest.mark.asyncio
async def test_write_overwrites_existing_file(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    await write.execute(path=str(f), content="new content")
    assert f.read_text() == "new content"


def test_write_definition_has_required_fields():
    d = write.DEFINITION
    assert d["name"] == "write_file"
    assert "path" in d["input_schema"]["properties"]
    assert "content" in d["input_schema"]["properties"]
    assert "path" in d["input_schema"]["required"]
    assert "content" in d["input_schema"]["required"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/tools/test_file_tools.py -v
```

Expected: `ERROR ... ModuleNotFoundError: No module named 'jarvis.tools.read'`

- [ ] **Step 3: Write `jarvis/tools/read.py`**

```python
DEFINITION = {
    "name": "read_file",
    "description": "Read the full contents of a file from disk. Returns the content as a string.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file.",
            }
        },
        "required": ["path"],
    },
}


async def execute(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"
```

- [ ] **Step 4: Write `jarvis/tools/write.py`**

```python
import os

DEFINITION = {
    "name": "write_file",
    "description": (
        "Write content to a file, creating it if it does not exist. "
        "Overwrites existing content. Creates parent directories as needed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to write to.",
            },
            "content": {
                "type": "string",
                "description": "Full content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
}


async def execute(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/tools/test_file_tools.py -v
```

Expected:
```
PASSED tests/tools/test_file_tools.py::test_read_existing_file
PASSED tests/tools/test_file_tools.py::test_read_missing_file
PASSED tests/tools/test_file_tools.py::test_read_definition_has_required_fields
PASSED tests/tools/test_file_tools.py::test_write_creates_file
PASSED tests/tools/test_file_tools.py::test_write_creates_parent_directories
PASSED tests/tools/test_file_tools.py::test_write_overwrites_existing_file
PASSED tests/tools/test_file_tools.py::test_write_definition_has_required_fields
7 passed
```

- [ ] **Step 6: Commit**

```bash
git add jarvis/tools/read.py jarvis/tools/write.py tests/tools/test_file_tools.py
git commit -m "feat: file tools — read_file and write_file"
git push
```

---

### Task 5: Bash Tool

**Files:**
- Create: `jarvis/tools/bash.py`
- Create: `tests/tools/test_bash.py`

**Interfaces:**
- Produces: `jarvis.tools.bash.execute(command: str) -> str`
- Produces: `jarvis.tools.bash.DEFINITION: dict`

- [ ] **Step 1: Write failing tests**

`tests/tools/test_bash.py`:
```python
import pytest
from jarvis.tools import bash


@pytest.mark.asyncio
async def test_bash_runs_command():
    result = await bash.execute(command="echo hello")
    assert "hello" in result


@pytest.mark.asyncio
async def test_bash_captures_stderr():
    result = await bash.execute(command="echo err >&2")
    assert "err" in result


@pytest.mark.asyncio
async def test_bash_nonzero_exit_still_returns_output():
    result = await bash.execute(command="ls /nonexistent_path_xyz 2>&1; true")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_bash_returns_no_output_message_when_silent():
    result = await bash.execute(command="true")
    assert isinstance(result, str)


def test_bash_definition_has_required_fields():
    d = bash.DEFINITION
    assert d["name"] == "bash"
    assert "command" in d["input_schema"]["properties"]
    assert "command" in d["input_schema"]["required"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/tools/test_bash.py -v
```

Expected: `ERROR ... ModuleNotFoundError: No module named 'jarvis.tools.bash'`

- [ ] **Step 3: Write `jarvis/tools/bash.py`**

```python
import asyncio

DEFINITION = {
    "name": "bash",
    "description": (
        "Execute a shell command and return its stdout and stderr. "
        "Use for running tests, git operations, package managers, or any CLI task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            }
        },
        "required": ["command"],
    },
}


async def execute(command: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()
    if stderr:
        output += "\n[stderr]\n" + stderr.decode()
    return output.strip() or "(no output)"
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/tools/test_bash.py -v
```

Expected:
```
PASSED tests/tools/test_bash.py::test_bash_runs_command
PASSED tests/tools/test_bash.py::test_bash_captures_stderr
PASSED tests/tools/test_bash.py::test_bash_nonzero_exit_still_returns_output
PASSED tests/tools/test_bash.py::test_bash_returns_no_output_message_when_silent
PASSED tests/tools/test_bash.py::test_bash_definition_has_required_fields
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add jarvis/tools/bash.py tests/tools/test_bash.py
git commit -m "feat: bash tool — async subprocess shell execution"
git push
```

---

### Task 6: Tool Registry + Query Engine

**Files:**
- Modify: `jarvis/tools/__init__.py`
- Create: `jarvis/query.py`
- Create: `tests/test_query.py`

**Interfaces:**
- Consumes: `jarvis.tools.read.DEFINITION`, `jarvis.tools.write.DEFINITION`, `jarvis.tools.bash.DEFINITION`
- Consumes: `jarvis.tools.read.execute`, `jarvis.tools.write.execute`, `jarvis.tools.bash.execute`
- Consumes: `Config` from `jarvis.config`
- Consumes: `History` from `jarvis.history`
- Produces: `ALL: list[dict]` from `jarvis.tools` — tool definitions sent to the API
- Produces: `EXECUTORS: dict[str, Callable]` from `jarvis.tools` — name → async executor
- Produces: `run_turn(history: History, config: Config) -> None` from `jarvis.query`

- [ ] **Step 1: Write failing tests**

`tests/test_query.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from jarvis.config import Config
from jarvis.history import History
from jarvis.tools import ALL, EXECUTORS


def test_tool_registry_has_all_tools():
    names = {t["name"] for t in ALL}
    assert names == {"read_file", "write_file", "bash"}


def test_executors_keys_match_tool_names():
    assert set(EXECUTORS.keys()) == {"read_file", "write_file", "bash"}


@pytest.mark.asyncio
async def test_run_turn_text_response(monkeypatch):
    """Query engine streams text and appends assistant message to history."""
    from jarvis import query

    config = Config(api_key="sk-test", model="claude-sonnet-4-6")
    history = History()
    history.append_user("say hello")

    # Build a mock message with text-only response
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello!"

    final_message = MagicMock()
    final_message.stop_reason = "end_turn"
    final_message.content = [text_block]

    mock_stream = AsyncMock()
    mock_stream.__aenter__ = AsyncMock(return_value=mock_stream)
    mock_stream.__aexit__ = AsyncMock(return_value=None)
    mock_stream.text_stream = _async_iter(["Hello", "!"])
    mock_stream.get_final_message = AsyncMock(return_value=final_message)

    mock_client = MagicMock()
    mock_client.messages.stream.return_value = mock_stream

    with patch("jarvis.query.anthropic.AsyncAnthropic", return_value=mock_client):
        await query.run_turn(history, config)

    msgs = history.messages
    assert msgs[-1]["role"] == "assistant"
    assert msgs[-1]["content"][0]["text"] == "Hello!"


@pytest.mark.asyncio
async def test_run_turn_tool_use_then_text(monkeypatch):
    """Query engine executes tool call and loops back to get final text."""
    from jarvis import query

    config = Config(api_key="sk-test", model="claude-sonnet-4-6")
    history = History()
    history.append_user("read /tmp/x.txt")

    # First response: tool_use
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_001"
    tool_block.name = "read_file"
    tool_block.input = {"path": "/tmp/x.txt"}

    tool_message = MagicMock()
    tool_message.stop_reason = "tool_use"
    tool_message.content = [tool_block]

    # Second response: text
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "The file contains: hello"

    final_message = MagicMock()
    final_message.stop_reason = "end_turn"
    final_message.content = [text_block]

    stream1 = AsyncMock()
    stream1.__aenter__ = AsyncMock(return_value=stream1)
    stream1.__aexit__ = AsyncMock(return_value=None)
    stream1.text_stream = _async_iter([])
    stream1.get_final_message = AsyncMock(return_value=tool_message)

    stream2 = AsyncMock()
    stream2.__aenter__ = AsyncMock(return_value=stream2)
    stream2.__aexit__ = AsyncMock(return_value=None)
    stream2.text_stream = _async_iter(["The file contains: hello"])
    stream2.get_final_message = AsyncMock(return_value=final_message)

    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = [stream1, stream2]

    fake_executor = AsyncMock(return_value="hello")

    with (
        patch("jarvis.query.anthropic.AsyncAnthropic", return_value=mock_client),
        patch.dict("jarvis.tools.EXECUTORS", {"read_file": fake_executor}),
    ):
        await query.run_turn(history, config)

    fake_executor.assert_awaited_once_with(path="/tmp/x.txt")
    msgs = history.messages
    roles = [m["role"] for m in msgs]
    assert roles == ["user", "assistant", "user", "assistant"]


async def _async_iter(items):
    for item in items:
        yield item
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_query.py -v
```

Expected: `ERROR ... cannot import name 'EXECUTORS' from 'jarvis.tools'`

- [ ] **Step 3: Write `jarvis/tools/__init__.py`**

```python
from . import bash, read, write

ALL = [read.DEFINITION, write.DEFINITION, bash.DEFINITION]

EXECUTORS: dict = {
    "read_file": read.execute,
    "write_file": write.execute,
    "bash": bash.execute,
}
```

- [ ] **Step 4: Write `jarvis/query.py`**

```python
import anthropic
from . import persona, tools
from .config import Config
from .history import History


async def run_turn(history: History, config: Config) -> None:
    client = anthropic.AsyncAnthropic(api_key=config.api_key)

    while True:
        async with client.messages.stream(
            model=config.model,
            system=persona.SYSTEM_PROMPT,
            tools=tools.ALL,
            messages=history.messages,
            max_tokens=8096,
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
            message = await stream.get_final_message()

        print()
        history.append_assistant_message(message)

        if message.stop_reason != "tool_use":
            break

        tool_results = []
        for block in message.content:
            if block.type != "tool_use":
                continue
            executor = tools.EXECUTORS.get(block.name)
            print(f"\n[{block.name}] running...", flush=True)
            if executor:
                result = await executor(**block.input)
            else:
                result = f"Error: unknown tool '{block.name}'"
            tool_results.append({"tool_use_id": block.id, "content": result})

        history.append_tool_results(tool_results)
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_query.py -v
```

Expected:
```
PASSED tests/test_query.py::test_tool_registry_has_all_tools
PASSED tests/test_query.py::test_executors_keys_match_tool_names
PASSED tests/test_query.py::test_run_turn_text_response
PASSED tests/test_query.py::test_run_turn_tool_use_then_text
4 passed
```

- [ ] **Step 6: Commit**

```bash
git add jarvis/tools/__init__.py jarvis/query.py tests/test_query.py
git commit -m "feat: tool registry and query engine with streaming tool-call loop"
git push
```

---

### Task 7: Commands

**Files:**
- Create: `jarvis/commands.py`
- Create: `tests/test_commands.py`

**Interfaces:**
- Consumes: `History` from `jarvis.history`
- Produces: `handle(input_str: str, history: History) -> bool` — returns `True` if input was a slash command (caller should skip LLM), raises `SystemExit` for `/exit`

- [ ] **Step 1: Write failing tests**

`tests/test_commands.py`:
```python
import pytest
from jarvis.commands import handle
from jarvis.history import History


def test_non_command_returns_false():
    h = History()
    assert handle("hello world", h) is False


def test_help_returns_true(capsys):
    h = History()
    result = handle("/help", h)
    assert result is True
    out = capsys.readouterr().out
    assert "/help" in out
    assert "/clear" in out
    assert "/exit" in out


def test_clear_resets_history(capsys):
    h = History()
    h.append_user("hi")
    result = handle("/clear", h)
    assert result is True
    assert h.messages == []
    out = capsys.readouterr().out
    assert "cleared" in out.lower()


def test_exit_raises_system_exit():
    h = History()
    with pytest.raises(SystemExit):
        handle("/exit", h)


def test_unknown_command_returns_true_with_message(capsys):
    h = History()
    result = handle("/unknown", h)
    assert result is True
    out = capsys.readouterr().out
    assert "unknown" in out.lower() or "/unknown" in out
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_commands.py -v
```

Expected: `ERROR ... ModuleNotFoundError: No module named 'jarvis.commands'`

- [ ] **Step 3: Write `jarvis/commands.py`**

```python
from .history import History

_HELP_TEXT = """\
Commands:
  /help   Show this message
  /clear  Reset conversation history
  /exit   Quit Jarvis\
"""


def handle(input_str: str, history: History) -> bool:
    if not input_str.startswith("/"):
        return False

    cmd = input_str.strip().split()[0].lower()

    match cmd:
        case "/help":
            print(_HELP_TEXT)
        case "/clear":
            history.clear()
            print("Conversation cleared.")
        case "/exit":
            print("Goodbye.")
            raise SystemExit(0)
        case _:
            print(f"Unknown command: {cmd}. Type /help for available commands.")

    return True
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_commands.py -v
```

Expected:
```
PASSED tests/test_commands.py::test_non_command_returns_false
PASSED tests/test_commands.py::test_help_returns_true
PASSED tests/test_commands.py::test_clear_resets_history
PASSED tests/test_commands.py::test_exit_raises_system_exit
PASSED tests/test_commands.py::test_unknown_command_returns_true_with_message
5 passed
```

- [ ] **Step 5: Commit**

```bash
git add jarvis/commands.py tests/test_commands.py
git commit -m "feat: slash command router (/help, /clear, /exit)"
git push
```

---

### Task 8: Main REPL

**Files:**
- Create: `jarvis/main.py`
- Create: `tests/test_main.py`

**Interfaces:**
- Consumes: `load_config` from `jarvis.config`
- Consumes: `History` from `jarvis.history`
- Consumes: `handle` from `jarvis.commands`
- Consumes: `run_turn` from `jarvis.query`
- Produces: `run() -> None` — sync entry point called by `jarvis` CLI script

- [ ] **Step 1: Write failing tests**

`tests/test_main.py`:
```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from jarvis.main import main


@pytest.mark.asyncio
async def test_main_routes_slash_command(monkeypatch):
    """/clear is handled locally without calling the query engine."""
    inputs = iter(["/clear", "/exit"])
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

    with (
        patch("jarvis.main.asyncio.get_event_loop") as mock_loop,
        patch("jarvis.main.query.run_turn", new_callable=AsyncMock) as mock_query,
    ):
        mock_loop.return_value.run_in_executor = AsyncMock(
            side_effect=lambda _, fn: _resolve(fn)
        )
        with pytest.raises(SystemExit):
            await main()

    mock_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_sends_user_message_to_query(monkeypatch):
    """Non-command input is appended to history and passed to query engine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    call_count = 0

    async def fake_run_in_executor(_, fn):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "read my config"
        raise EOFError

    with (
        patch("jarvis.main.asyncio.get_event_loop") as mock_loop,
        patch("jarvis.main.query.run_turn", new_callable=AsyncMock) as mock_query,
    ):
        mock_loop.return_value.run_in_executor = fake_run_in_executor
        await main()

    mock_query.assert_awaited_once()


async def _resolve(fn):
    return fn()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_main.py -v
```

Expected: `ERROR ... ModuleNotFoundError: No module named 'jarvis.main'`

- [ ] **Step 3: Write `jarvis/main.py`**

```python
import asyncio
import argparse
from . import query
from .commands import handle
from .config import load_config
from .history import History


async def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis Code — AI coding assistant")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model ID")
    args = parser.parse_args()

    config = load_config(model=args.model)
    history = History()
    loop = asyncio.get_event_loop()

    print("Jarvis Code. Type /help for commands, Ctrl-C or /exit to quit.\n")

    while True:
        try:
            user_input = await loop.run_in_executor(
                None, lambda: input("> ").strip()
            )
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if handle(user_input, history):
            continue

        history.append_user(user_input)

        try:
            await query.run_turn(history, config)
        except Exception as e:
            print(f"\nError: {e}")


def run() -> None:
    asyncio.run(main())
```

- [ ] **Step 4: Run all tests to verify everything passes**

```bash
pytest -v
```

Expected:
```
PASSED tests/test_config.py::test_missing_api_key_raises
PASSED tests/test_config.py::test_load_config_returns_config
PASSED tests/test_config.py::test_load_config_custom_model
PASSED tests/test_history.py::test_append_user_adds_user_message
PASSED tests/test_history.py::test_clear_empties_history
PASSED tests/test_history.py::test_messages_returns_copy
PASSED tests/test_history.py::test_append_tool_results_adds_user_message_with_tool_results
PASSED tests/test_history.py::test_append_assistant_message_text_only
PASSED tests/test_history.py::test_append_assistant_message_with_tool_use
PASSED tests/tools/test_file_tools.py::test_read_existing_file
PASSED tests/tools/test_file_tools.py::test_read_missing_file
PASSED tests/tools/test_file_tools.py::test_read_definition_has_required_fields
PASSED tests/tools/test_file_tools.py::test_write_creates_file
PASSED tests/tools/test_file_tools.py::test_write_creates_parent_directories
PASSED tests/tools/test_file_tools.py::test_write_overwrites_existing_file
PASSED tests/tools/test_file_tools.py::test_write_definition_has_required_fields
PASSED tests/tools/test_bash.py::test_bash_runs_command
PASSED tests/tools/test_bash.py::test_bash_captures_stderr
PASSED tests/tools/test_bash.py::test_bash_nonzero_exit_still_returns_output
PASSED tests/tools/test_bash.py::test_bash_returns_no_output_message_when_silent
PASSED tests/tools/test_bash.py::test_bash_definition_has_required_fields
PASSED tests/test_query.py::test_tool_registry_has_all_tools
PASSED tests/test_query.py::test_executors_keys_match_tool_names
PASSED tests/test_query.py::test_run_turn_text_response
PASSED tests/test_query.py::test_run_turn_tool_use_then_text
PASSED tests/test_commands.py::test_non_command_returns_false
PASSED tests/test_commands.py::test_help_returns_true
PASSED tests/test_commands.py::test_clear_resets_history
PASSED tests/test_commands.py::test_exit_raises_system_exit
PASSED tests/test_commands.py::test_unknown_command_returns_true_with_message
PASSED tests/test_main.py::test_main_routes_slash_command
PASSED tests/test_main.py::test_main_sends_user_message_to_query
32 passed
```

- [ ] **Step 5: Smoke test the running CLI**

```bash
export ANTHROPIC_API_KEY=your_key_here
jarvis
```

Type `/help` — expect to see the command list.
Type `/exit` — expect clean exit.

- [ ] **Step 6: Commit and push**

```bash
git add jarvis/main.py tests/test_main.py
git commit -m "feat: async REPL main loop — wires config, history, commands, query"
git push
```
