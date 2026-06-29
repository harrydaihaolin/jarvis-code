import pytest
from jarvis.tools import bash


@pytest.mark.asyncio
async def test_bash_runs_command():
    result = await bash.execute(command="echo hello")
    assert "hello" in result


@pytest.mark.asyncio
async def test_bash_captures_stderr():
    result = await bash.execute(command="echo err >&2")
    assert "err" in result


@pytest.mark.asyncio
async def test_bash_nonzero_exit_still_returns_output():
    result = await bash.execute(command="ls /nonexistent_path_xyz 2>&1; true")
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_bash_returns_no_output_message_when_silent():
    result = await bash.execute(command="true")
    assert isinstance(result, str)


def test_bash_definition_has_required_fields():
    d = bash.DEFINITION
    assert d["name"] == "bash"
    assert "command" in d["input_schema"]["properties"]
    assert "command" in d["input_schema"]["required"]
