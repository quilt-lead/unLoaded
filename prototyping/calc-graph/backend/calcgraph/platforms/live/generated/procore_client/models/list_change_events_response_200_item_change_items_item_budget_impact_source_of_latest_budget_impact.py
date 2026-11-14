from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact(
    StrEnum
):
    BUDGET_CHANGE = "budget_change"
    ESTIMATE = "estimate"

    def __str__(self) -> str:
        return str(self.value)
