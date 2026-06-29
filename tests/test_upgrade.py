from unittest.mock import patch, MagicMock

import jarvis.main as jmain
from jarvis import upgrade as upgrade_mod


def test_upgrade_invokes_uv_tool_install():
    with (
        patch("jarvis.upgrade.shutil.which", return_value="/usr/bin/uv"),
        patch("jarvis.upgrade.subprocess.run", return_value=MagicMock(returncode=0)) as mock_run,
    ):
        rc = upgrade_mod.upgrade()

    assert rc == 0
    args = mock_run.call_args.args[0]
    assert args[:3] == ["uv", "tool", "install"]
    assert "--reinstall" in args
    assert upgrade_mod.REPO_URL in args


def test_upgrade_errors_without_uv():
    with (
        patch("jarvis.upgrade.shutil.which", return_value=None),
        patch("jarvis.upgrade.subprocess.run") as mock_run,
    ):
        rc = upgrade_mod.upgrade()

    assert rc == 1
    mock_run.assert_not_called()


def test_upgrade_propagates_failure():
    with (
        patch("jarvis.upgrade.shutil.which", return_value="/usr/bin/uv"),
        patch("jarvis.upgrade.subprocess.run", return_value=MagicMock(returncode=7)),
    ):
        assert upgrade_mod.upgrade() == 7


def test_run_dispatches_upgrade_subcommand(monkeypatch):
    monkeypatch.setattr("sys.argv", ["jarvis", "upgrade"])
    with patch("jarvis.upgrade.upgrade", return_value=0) as mock_upgrade:
        try:
            jmain.run()
        except SystemExit as e:
            assert e.code == 0
    mock_upgrade.assert_called_once()


def test_run_without_subcommand_starts_repl(monkeypatch):
    monkeypatch.setattr("sys.argv", ["jarvis"])
    with (
        patch("jarvis.main.main", new_callable=MagicMock) as mock_main,
        patch("jarvis.main.asyncio.run") as mock_async_run,
        patch("jarvis.upgrade.upgrade") as mock_upgrade,
    ):
        jmain.run()
    mock_main.assert_called_once()
    mock_async_run.assert_called_once()
    mock_upgrade.assert_not_called()
