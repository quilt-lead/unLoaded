from enum import StrEnum


class ProcoreChangeEventChangeItemsItemLatestRevenueValuesCalculationStrategy(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
