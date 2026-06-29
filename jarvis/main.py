import asyncio
import argparse
from . import query
from .commands import handle
from .config import load_config
from .history import History


async def main() -> None:
    parser = argparse.ArgumentParser(description="Jarvis Code — AI coding assistant")
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model ID")
    args, _ = parser.parse_known_args()  # parse_args() would sys.exit(2) when pytest injects its own args

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
