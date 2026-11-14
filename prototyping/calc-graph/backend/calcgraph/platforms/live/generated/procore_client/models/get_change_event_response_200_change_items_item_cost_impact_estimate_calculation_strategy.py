from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemCostImpactEstimateCalculationStrategy(
    StrEnum
):
    AUTOMATIC = "automatic"
    MANUAL = "manual"

    def __str__(self) -> str:
        return str(self.value)
