from enum import StrEnum


class CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"

    def __str__(self) -> str:
        return str(self.value)
