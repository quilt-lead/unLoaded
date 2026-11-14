from enum import StrEnum


class ListTasksView(StrEnum):
    COMPACT = "compact"
    NORMAL = "normal"

    def __str__(self) -> str:
        return str(self.value)
