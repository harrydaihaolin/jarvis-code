import os
import pytest
from jarvis.tools import read, write


@pytest.mark.asyncio
async def test_read_existing_file(tmp_path):
    f = tmp_path / "hello.txt"
    f.write_text("hello world")
    result = await read.execute(path=str(f))
    assert result == "hello world"


@pytest.mark.asyncio
async def test_read_missing_file():
    result = await read.execute(path="/nonexistent/path/file.txt")
    assert "not found" in result.lower() or "error" in result.lower()


def test_read_definition_has_required_fields():
    d = read.DEFINITION
    assert d["name"] == "read_file"
    assert "path" in d["input_schema"]["properties"]
    assert "path" in d["input_schema"]["required"]


@pytest.mark.asyncio
async def test_write_creates_file(tmp_path):
    path = str(tmp_path / "output.txt")
    result = await write.execute(path=path, content="written content")
    assert os.path.exists(path)
    assert open(path).read() == "written content"
    assert "written" in result.lower() or str(path) in result


@pytest.mark.asyncio
async def test_write_creates_parent_directories(tmp_path):
    path = str(tmp_path / "nested" / "deep" / "file.txt")
    await write.execute(path=path, content="deep file")
    assert os.path.exists(path)


@pytest.mark.asyncio
async def test_write_overwrites_existing_file(tmp_path):
    f = tmp_path / "existing.txt"
    f.write_text("old content")
    await write.execute(path=str(f), content="new content")
    assert f.read_text() == "new content"


def test_write_definition_has_required_fields():
    d = write.DEFINITION
    assert d["name"] == "write_file"
    assert "path" in d["input_schema"]["properties"]
    assert "content" in d["input_schema"]["properties"]
    assert "path" in d["input_schema"]["required"]
    assert "content" in d["input_schema"]["required"]
