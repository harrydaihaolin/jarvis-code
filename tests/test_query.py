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
