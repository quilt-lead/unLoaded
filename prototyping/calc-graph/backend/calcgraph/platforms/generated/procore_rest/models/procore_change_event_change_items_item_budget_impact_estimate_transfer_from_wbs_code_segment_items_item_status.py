from enum import StrEnum


class ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
