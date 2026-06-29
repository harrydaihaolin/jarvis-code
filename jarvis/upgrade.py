import shutil
import subprocess
import sys
from importlib import metadata

PACKAGE_NAME = "jarvis-code"
REPO_URL = "git+https://github.com/harrydaihaolin/jarvis-code.git"


def _current_version() -> str:
    try:
        return metadata.version(PACKAGE_NAME)
    except metadata.PackageNotFoundError:
        return "unknown"


def upgrade() -> int:
    """Reinstall the Jarvis CLI from the latest commit on the default branch.

    Jarvis is distributed as a uv tool, so the upgrade simply re-runs
    ``uv tool install`` against the git remote with cache refresh + force
    so the newest published commit replaces the current install.
    """
    if shutil.which("uv") is None:
        print(
            "Error: 'uv' was not found on PATH. Jarvis is installed as a uv "
            "tool; install uv first: https://docs.astral.sh/uv/",
            file=sys.stderr,
        )
        return 1

    print(f"Jarvis {_current_version()} — upgrading to the latest version...")

    # --reinstall forces a rebuild from the newest commit even though the
    # package version is unchanged; --refresh busts uv's git/source cache.
    cmd = ["uv", "tool", "install", "--reinstall", "--refresh", REPO_URL]
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("Upgrade failed. See the output above for details.", file=sys.stderr)
        return result.returncode

    print("Jarvis upgraded successfully. Start a new session to use the latest version.")
    return 0
