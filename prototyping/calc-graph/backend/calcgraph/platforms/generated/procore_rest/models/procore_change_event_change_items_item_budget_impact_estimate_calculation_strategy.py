from enum import StrEnum


class ProcoreChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
