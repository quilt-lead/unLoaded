from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemLatestRevenueValuesCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
