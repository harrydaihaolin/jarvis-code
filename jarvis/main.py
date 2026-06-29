import asyncio
import argparse
import os
import signal
import sys
from . import query
from .commands import handle
from .config import load_config
from .history import History


async def _read_line(prompt: str) -> str:
    """Read one line from stdin without blocking the event loop.

    The line is read via the loop's reader on the stdin fd rather than a
    worker thread, so a SIGINT-driven cancellation returns immediately.
    A blocked ``run_in_executor(input)`` would otherwise stall shutdown
    until the user pressed Enter.
    """
    loop = asyncio.get_running_loop()
    fd = sys.stdin.fileno()
    fut: asyncio.Future[str] = loop.create_future()
    buffer = bytearray()

    def on_readable() -> None:
        try:
            chunk = os.read(fd, 4096)
        except (BlockingIOError, InterruptedError):
            return
        if not chunk:  # Ctrl-D / EOF
            if not fut.done():
                fut.set_exception(EOFError())
            return
        buffer.extend(chunk)
        newline = buffer.find(b"\n")
        if newline != -1 and not fut.done():
            fut.set_result(buffer[:newline].decode(errors="replace"))

    print(prompt, end="", flush=True)
    loop.add_reader(fd, on_readable)
    try:
        return await fut
    finally:
        loop.remove_reader(fd)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Jarvis Code — AI coding assistant",
        epilog="subcommands:\n  upgrade    upgrade Jarvis to the latest version",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--model", default="claude-sonnet-4-6", help="Claude model ID")
    args, _ = parser.parse_known_args()  # parse_args() would sys.exit(2) when pytest injects its own args

    config = load_config(model=args.model)
    history = History()
    loop = asyncio.get_running_loop()

    current_turn: asyncio.Task | None = None
    input_task: asyncio.Task | None = None

    def on_sigint() -> None:
        if current_turn is not None and not current_turn.done():
            # Ctrl-C mid-turn cancels just the in-flight response, keeping the REPL alive.
            current_turn.cancel()
        elif input_task is not None and not input_task.done():
            # Ctrl-C at an idle prompt cancels the read so we can exit gracefully.
            input_task.cancel()

    try:
        loop.add_signal_handler(signal.SIGINT, on_sigint)
    except NotImplementedError:
        pass  # platforms without signal-handler support fall back to default KeyboardInterrupt

    print("Jarvis Code. Type /help for commands, Ctrl-C to interrupt, /exit to quit.\n")

    while True:
        input_task = asyncio.ensure_future(_read_line("> "))
        try:
            user_input = (await input_task).strip()
        except (EOFError, asyncio.CancelledError, KeyboardInterrupt):
            print("\nGoodbye.")
            break

        if not user_input:
            continue

        if handle(user_input, history, config):   # config forwarded for /btw
            continue

        history.append_user(user_input)

        current_turn = asyncio.ensure_future(query.run_turn(history, config))
        try:
            await current_turn
        except asyncio.CancelledError:
            print("\n[interrupted]")
        except Exception as e:
            print(f"\nError: {e}")
        finally:
            current_turn = None


def run() -> None:
    # Dispatch the `upgrade` subcommand before argparse so the REPL parser
    # (which only knows --model) stays unchanged.
    if sys.argv[1:2] == ["upgrade"]:
        from .upgrade import upgrade

        raise SystemExit(upgrade())

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
