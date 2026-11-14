from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfStage(StrEnum):
    BUDGET_CHANGE = "budget_change"
    ESTIMATE = "estimate"

    def __str__(self) -> str:
        return str(self.value)
