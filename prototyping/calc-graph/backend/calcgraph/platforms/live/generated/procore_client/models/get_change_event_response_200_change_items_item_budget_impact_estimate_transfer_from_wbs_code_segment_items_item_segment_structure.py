from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItemSegmentStructure(
    StrEnum
):
    FLAT = "flat"
    TIERED = "tiered"

    def __str__(self) -> str:
        return str(self.value)
