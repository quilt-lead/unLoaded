from enum import StrEnum


class ListChangeEventsResponse200ItemProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
