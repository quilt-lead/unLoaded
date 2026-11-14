from enum import StrEnum


class ListProjectsView(StrEnum):
    COMPACT = "compact"
    EXTENDED = "extended"
    IDS = "ids"
    NORMAL = "normal"

    def __str__(self) -> str:
        return str(self.value)
