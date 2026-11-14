from enum import StrEnum


class ProcoreChangeEventChangeItemsItemBudgetImpactSourceOfStage(StrEnum):
    BUDGET_CHANGE = "budget_change"
    ESTIMATE = "estimate"

    def __str__(self) -> str:
        return str(self.value)
