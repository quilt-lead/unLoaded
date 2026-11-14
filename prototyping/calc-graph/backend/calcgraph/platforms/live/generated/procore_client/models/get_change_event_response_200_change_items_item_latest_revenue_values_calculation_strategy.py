from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemLatestRevenueValuesCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
