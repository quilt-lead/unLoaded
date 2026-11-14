from enum import StrEnum


class PermissionLevel(StrEnum):
    CREATE = "create"
    READ = "read"
    WRITE = "write"

    def __str__(self) -> str:
        return str(self.value)
