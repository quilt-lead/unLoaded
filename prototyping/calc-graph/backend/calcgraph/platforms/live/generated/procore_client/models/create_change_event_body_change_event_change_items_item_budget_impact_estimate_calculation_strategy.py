from enum import StrEnum


class CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
