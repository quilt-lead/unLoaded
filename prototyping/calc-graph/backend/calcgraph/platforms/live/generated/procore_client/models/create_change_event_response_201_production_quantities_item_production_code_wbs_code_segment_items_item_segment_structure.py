from enum import StrEnum


class CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegmentStructure(
    StrEnum
):
    FLAT = "flat"
    TIERED = "tiered"

    def __str__(self) -> str:
        return str(self.value)
