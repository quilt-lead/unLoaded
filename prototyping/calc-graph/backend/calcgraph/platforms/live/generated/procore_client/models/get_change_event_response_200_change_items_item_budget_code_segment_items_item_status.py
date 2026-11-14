from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemBudgetCodeSegmentItemsItemStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
