import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from jarvis.main import main


@pytest.mark.asyncio
async def test_main_routes_slash_command(monkeypatch):
    """/clear is handled locally without calling the query engine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    inputs = iter(["/clear", "/exit"])

    async def fake_read_line(_prompt):
        return next(inputs)

    with (
        patch("jarvis.main._read_line", fake_read_line),
        patch("jarvis.main.query.run_turn", new_callable=AsyncMock) as mock_query,
    ):
        with pytest.raises(SystemExit):
            await main()

    mock_query.assert_not_awaited()


@pytest.mark.asyncio
async def test_main_sends_user_message_to_query(monkeypatch):
    """Non-command input is appended to history and passed to query engine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    inputs = iter(["read my config"])

    async def fake_read_line(_prompt):
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    with (
        patch("jarvis.main._read_line", fake_read_line),
        patch("jarvis.main.query.run_turn", new_callable=AsyncMock) as mock_query,
    ):
        await main()

    mock_query.assert_awaited_once()


@pytest.mark.asyncio
async def test_main_interrupt_during_turn_keeps_repl(monkeypatch):
    """Ctrl-C during a model turn cancels the turn but returns to the prompt."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    inputs = iter(["first message", "second message"])
    prompts_seen = 0

    async def fake_read_line(_prompt):
        nonlocal prompts_seen
        prompts_seen += 1
        try:
            return next(inputs)
        except StopIteration:
            raise EOFError

    async def cancelled_turn(*_args, **_kwargs):
        raise asyncio.CancelledError

    with (
        patch("jarvis.main._read_line", fake_read_line),
        patch("jarvis.main.query.run_turn", side_effect=cancelled_turn) as mock_query,
    ):
        await main()

    # Turn was attempted twice (interrupt didn't kill the REPL), then EOF exited.
    assert mock_query.await_count == 2
    assert prompts_seen == 3
