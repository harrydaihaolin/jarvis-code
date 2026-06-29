import pytest
from unittest.mock import patch
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


def test_help_includes_bang_docs(capsys):
    h = History()
    handle("/help", h)
    out = capsys.readouterr().out
    assert "!" in out


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


def test_bang_command_returns_true():
    h = History()
    # Output goes directly to the real terminal (not captured) — that's intentional
    result = handle("!echo hello", h)
    assert result is True


def test_bang_runs_command(capsys):
    """Shell command is dispatched; output streams directly to terminal."""
    h = History()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        handle("!ls -la", h)
        mock_run.assert_called_once_with("ls -la", shell=True, text=True, capture_output=False)


def test_bang_empty_command_shows_usage(capsys):
    h = History()
    result = handle("!", h)
    assert result is True
    out = capsys.readouterr().out
    assert "usage" in out.lower() or "!" in out


def test_bang_does_not_add_to_history():
    h = History()
    handle("!echo hello", h)
    assert h.messages == []


def test_bang_bad_exit_code_shows_code(capsys):
    h = History()
    handle("!exit 42", h)
    out = capsys.readouterr().out
    assert "42" in out


def test_bang_nonzero_exit_shows_code(capsys):
    h = History()
    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 1
        handle("!false", h)
    out = capsys.readouterr().out
    assert "1" in out
