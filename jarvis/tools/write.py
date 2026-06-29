import os

DEFINITION = {
    "name": "write_file",
    "description": (
        "Write content to a file, creating it if it does not exist. "
        "Overwrites existing content. Creates parent directories as needed."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Absolute or relative path to write to.",
            },
            "content": {
                "type": "string",
                "description": "Full content to write to the file.",
            },
        },
        "required": ["path", "content"],
    },
}


async def execute(path: str, content: str) -> str:
    try:
        parent = os.path.dirname(os.path.abspath(path))
        os.makedirs(parent, exist_ok=True)
        with open(path, "w") as f:
            f.write(content)
        return f"Written {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error writing {path}: {e}"
