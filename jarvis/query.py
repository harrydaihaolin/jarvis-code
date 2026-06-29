import anthropic
from . import persona, tools
from .config import Config
from .history import History


async def run_turn(history: History, config: Config) -> None:
    client = anthropic.AsyncAnthropic(api_key=config.api_key)

    while True:
        async with client.messages.stream(
            model=config.model,
            system=persona.SYSTEM_PROMPT,
            tools=tools.ALL,
            messages=history.messages,
            max_tokens=8096,
        ) as stream:
            async for text in stream.text_stream:
                print(text, end="", flush=True)
            message = await stream.get_final_message()

        print()
        history.append_assistant_message(message)

        if message.stop_reason != "tool_use":
            break

        tool_results = []
        for block in message.content:
            if block.type != "tool_use":
                continue
            executor = tools.EXECUTORS.get(block.name)
            print(f"\n[{block.name}] running...", flush=True)
            try:
                if executor:
                    result = await executor(**block.input)
                else:
                    result = f"Error: unknown tool '{block.name}'"
            except Exception as e:
                result = f"Error running {block.name}: {e}"
            tool_results.append({"tool_use_id": block.id, "content": result})

        if not tool_results:
            break
        history.append_tool_results(tool_results)
