from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimateCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
