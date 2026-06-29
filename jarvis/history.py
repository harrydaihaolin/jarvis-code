class History:
    def __init__(self) -> None:
        self._messages: list[dict] = []

    @property
    def messages(self) -> list[dict]:
        return list(self._messages)

    def append_user(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})

    def append_assistant_message(self, message) -> None:
        content = []
        for block in message.content:
            if block.type == "text":
                content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": dict(block.input),
                })
        self._messages.append({"role": "assistant", "content": content})

    def append_tool_results(self, results: list[dict]) -> None:
        content = [
            {
                "type": "tool_result",
                "tool_use_id": r["tool_use_id"],
                "content": r["content"],
            }
            for r in results
        ]
        self._messages.append({"role": "user", "content": content})

    def clear(self) -> None:
        self._messages.clear()
