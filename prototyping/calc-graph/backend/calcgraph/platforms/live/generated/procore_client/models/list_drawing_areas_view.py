from enum import StrEnum


class ListDrawingAreasView(StrEnum):
    COMPACT = "compact"
    EXTENDED = "extended"
    MFE = "mfe"
    ONLY_IDS = "only_ids"

    def __str__(self) -> str:
        return str(self.value)
