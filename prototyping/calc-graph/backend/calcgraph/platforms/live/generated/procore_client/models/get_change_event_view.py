from enum import StrEnum


class GetChangeEventView(StrEnum):
    EXCLUDE_CHANGE_ITEMS = "exclude_change_items"

    def __str__(self) -> str:
        return str(self.value)
