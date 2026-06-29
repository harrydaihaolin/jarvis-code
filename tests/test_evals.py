import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from jarvis.history import History
from evals.run import _turn_count


def _make_tool_result_msg():
    return {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "x", "content": "ok"}]}

def _make_user_msg(text="hi"):
    return {"role": "user", "content": text}

def _make_assistant_msg(text="hello"):
    return {"role": "assistant", "content": [{"type": "text", "text": text}]}


def test_turn_count_zero_no_tool_results():
    h = History()
    h.append_user("hello")
    assert _turn_count(h) == 0


def test_turn_count_zero_assistant_only():
    h = History()
    h.append_user("q")
    # manually inject assistant message with tool_use (not a tool_result user msg)
    h._messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {}}]})
    assert _turn_count(h) == 0


def test_turn_count_one_cycle():
    h = History()
    h.append_user("q")
    h._messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": "t1", "name": "bash", "input": {}}]})
    h._messages.append(_make_tool_result_msg())
    assert _turn_count(h) == 1


def test_turn_count_three_cycles():
    h = History()
    h.append_user("q")
    for i in range(3):
        h._messages.append({"role": "assistant", "content": [{"type": "tool_use", "id": f"t{i}", "name": "bash", "input": {}}]})
        h._messages.append(_make_tool_result_msg())
    assert _turn_count(h) == 3


def test_turn_count_ignores_plain_user_messages():
    h = History()
    h.append_user("first")
    h.append_user("second")   # plain string content, not a list
    assert _turn_count(h) == 0
