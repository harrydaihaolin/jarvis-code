import subprocess
from .history import History
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

_HELP_TEXT = """\
Commands:
  /help   Show this message
  /clear  Reset conversation history
  /btw    Spawn a background sub-agent for a side question (e.g. /btw what is X?)
  /exit   Quit Jarvis

Shell execution:
  !<cmd>  Run a shell command directly (e.g. !ls -la)\
"""


def handle(input_str: str, history: History, config: "Config | None" = None) -> bool:
    if input_str.startswith("!"):
        _run_shell(input_str[1:].strip())
        return True

    if not input_str.startswith("/"):
        return False

    parts = input_str.strip().split(maxsplit=1)
    cmd = parts[0].lower()
    rest = parts[1] if len(parts) > 1 else ""

    match cmd:
        case "/help":
            print(_HELP_TEXT)
        case "/clear":
            history.clear()
            print("Conversation cleared.")
        case "/btw":
            _handle_btw(rest, config)
        case "/exit":
            print("Goodbye.")
            raise SystemExit(0)
        case _:
            print(f"Unknown command: {cmd}. Type /help for available commands.")

    return True


# ── /btw ─────────────────────────────────────────────────────────────────────

def _handle_btw(question: str, config: "Config | None") -> None:
    if not question.strip():
        print("Usage: /btw <question>  (e.g. /btw what does os.path.join return?)")
        return
    if config is None:
        print("[btw] No config available — cannot spawn sub-agent.")
        return

    from .skills.btw import spawn
    task = spawn(question.strip(), config)
    # Task runs freely in the background; we give the user a quick confirmation.
    print(f"[btw] Sub-agent spawned for: \"{question.strip()}\" (task id={id(task):#x})")


# ── !shell ────────────────────────────────────────────────────────────────────

def _run_shell(command: str) -> None:
    if not command:
        print("Usage: !<command>  (e.g. !ls -la)")
        return
    try:
        result = subprocess.run(command, shell=True, text=True, capture_output=False)
        if result.returncode != 0:
            print(f"[exited with code {result.returncode}]")
    except Exception as e:
        print(f"Error running command: {e}")
