from enum import StrEnum


class CreateChangeEventResponse201ChangeItemsItemLatestCostValuesCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
