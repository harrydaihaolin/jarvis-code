from . import bash, read, write
from typing import Callable

_TOOLS: list[tuple[dict, Callable]] = [
    (read.DEFINITION, read.execute),
    (write.DEFINITION, write.execute),
    (bash.DEFINITION, bash.execute),
]

ALL: list[dict] = [defn for defn, _ in _TOOLS]
EXECUTORS: dict[str, Callable] = {defn["name"]: fn for defn, fn in _TOOLS}
