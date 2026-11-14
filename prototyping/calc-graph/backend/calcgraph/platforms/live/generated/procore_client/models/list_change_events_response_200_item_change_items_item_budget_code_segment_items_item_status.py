from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemBudgetCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
