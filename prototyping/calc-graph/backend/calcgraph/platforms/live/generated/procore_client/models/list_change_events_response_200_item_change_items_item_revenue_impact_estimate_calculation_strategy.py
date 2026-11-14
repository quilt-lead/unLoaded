from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemRevenueImpactEstimateCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
