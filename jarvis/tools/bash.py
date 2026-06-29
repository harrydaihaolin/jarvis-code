import asyncio

DEFINITION = {
    "name": "bash",
    "description": (
        "Execute a shell command and return its stdout and stderr. "
        "Use for running tests, git operations, package managers, or any CLI task."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "The shell command to execute.",
            }
        },
        "required": ["command"],
    },
}


async def execute(command: str) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    output = stdout.decode()
    if stderr:
        output += "\n[stderr]\n" + stderr.decode()
    return output.strip() or "(no output)"
