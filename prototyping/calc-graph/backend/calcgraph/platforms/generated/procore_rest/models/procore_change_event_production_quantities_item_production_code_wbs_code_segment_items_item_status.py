from enum import StrEnum


class ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
