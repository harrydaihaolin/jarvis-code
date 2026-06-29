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
