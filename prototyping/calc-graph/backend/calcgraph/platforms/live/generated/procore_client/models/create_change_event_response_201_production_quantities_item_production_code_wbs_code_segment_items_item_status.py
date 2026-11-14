from enum import StrEnum


class CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
