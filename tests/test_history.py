from unittest.mock import MagicMock
from jarvis.history import History


def test_append_user_adds_user_message():
    h = History()
    h.append_user("hello")
    assert h.messages == [{"role": "user", "content": "hello"}]


def test_clear_empties_history():
    h = History()
    h.append_user("hello")
    h.clear()
    assert h.messages == []


def test_messages_returns_copy():
    h = History()
    h.append_user("hello")
    msgs = h.messages
    msgs.append({"role": "user", "content": "injected"})
    assert len(h.messages) == 1


def test_append_tool_results_adds_user_message_with_tool_results():
    h = History()
    results = [
        {"tool_use_id": "toolu_001", "content": "file contents here"},
        {"tool_use_id": "toolu_002", "content": "command output"},
    ]
    h.append_tool_results(results)
    assert h.messages == [
        {
            "role": "user",
            "content": [
                {"type": "tool_result", "tool_use_id": "toolu_001", "content": "file contents here"},
                {"type": "tool_result", "tool_use_id": "toolu_002", "content": "command output"},
            ],
        }
    ]


def test_append_assistant_message_text_only():
    h = History()
    message = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Hello, I can help!"
    message.content = [text_block]
    h.append_assistant_message(message)
    assert h.messages == [
        {"role": "assistant", "content": [{"type": "text", "text": "Hello, I can help!"}]}
    ]


def test_append_assistant_message_with_tool_use():
    h = History()
    message = MagicMock()
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "toolu_001"
    tool_block.name = "read_file"
    tool_block.input = {"path": "/tmp/foo.py"}
    message.content = [tool_block]
    h.append_assistant_message(message)
    assert h.messages == [
        {
            "role": "assistant",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_001",
                    "name": "read_file",
                    "input": {"path": "/tmp/foo.py"},
                }
            ],
        }
    ]
