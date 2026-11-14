from enum import StrEnum


class CreateChangeEventResponse201ChangeItemsItemLatestRevenueValuesCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
