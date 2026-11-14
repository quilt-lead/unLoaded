from enum import StrEnum


class ProcoreChangeEventChangeItemsItemLatestCostValuesCalculationStrategy(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
