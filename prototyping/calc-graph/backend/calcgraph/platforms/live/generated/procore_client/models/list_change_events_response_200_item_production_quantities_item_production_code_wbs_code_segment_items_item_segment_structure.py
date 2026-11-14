from enum import StrEnum


class ListChangeEventsResponse200ItemProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegmentStructure(
    StrEnum
):
    FLAT = "flat"
    TIERED = "tiered"

    def __str__(self) -> str:
        return str(self.value)
