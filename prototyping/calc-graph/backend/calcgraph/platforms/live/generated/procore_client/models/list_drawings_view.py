from enum import StrEnum


class ListDrawingsView(StrEnum):
    COMPACT = "compact"
    EXTENDED = "extended"
    WITH_REVISIONS = "with_revisions"

    def __str__(self) -> str:
        return str(self.value)
