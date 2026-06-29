DEFINITION = {
    "name": "read_file",
    "description": "Read the full contents of a file from disk. Returns the content as a string.",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to the file.",
            }
        },
        "required": ["path"],
    },
}


async def execute(path: str) -> str:
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: file not found: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"
