from enum import StrEnum


class ProcoreChangeEventMarkupItemsItemWbsCodeSegmentItemsItemStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
