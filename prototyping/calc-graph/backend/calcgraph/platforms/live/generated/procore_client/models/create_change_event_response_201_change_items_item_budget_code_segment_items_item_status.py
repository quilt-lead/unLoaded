from enum import StrEnum


class CreateChangeEventResponse201ChangeItemsItemBudgetCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
