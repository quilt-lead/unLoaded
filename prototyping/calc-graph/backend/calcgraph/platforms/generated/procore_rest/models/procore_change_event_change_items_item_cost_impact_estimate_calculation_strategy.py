from enum import StrEnum


class ProcoreChangeEventChangeItemsItemCostImpactEstimateCalculationStrategy(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
