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
