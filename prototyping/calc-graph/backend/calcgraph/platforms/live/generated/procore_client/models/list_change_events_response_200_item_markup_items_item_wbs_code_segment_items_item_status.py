from enum import StrEnum


class ListChangeEventsResponse200ItemMarkupItemsItemWbsCodeSegmentItemsItemStatus(
    StrEnum
):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
