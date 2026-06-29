from . import bash, read, write

ALL = [read.DEFINITION, write.DEFINITION, bash.DEFINITION]

EXECUTORS: dict = {
    "read_file": read.execute,
    "write_file": write.execute,
    "bash": bash.execute,
}
