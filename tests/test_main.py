import pytest
from unittest.mock import AsyncMock, patch
from jarvis.main import main


@pytest.mark.asyncio
async def test_main_routes_slash_command(monkeypatch):
    """/clear is handled locally without calling the query engine."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    call_count = 0

    async def fake_executor(_, fn):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return "/clear"
        return "/exit"

    with (
        patch("jarvis.main.asyncio.get_event_loop") as mock_loop,
        patch("jarvis.main.query.run_turn", new_callable=AsyncMock) as mock_query,
    ):
        mock_loop.return_value.run_in_executor = fake_executor
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
