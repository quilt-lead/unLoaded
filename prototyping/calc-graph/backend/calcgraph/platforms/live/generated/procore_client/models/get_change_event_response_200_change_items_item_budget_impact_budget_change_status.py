from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChangeStatus(StrEnum):
    APPROVED = "approved"
    DRAFT = "draft"
    UNDER_REVIEW = "under_review"
    VOID = "void"

    def __str__(self) -> str:
        return str(self.value)
