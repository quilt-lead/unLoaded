from enum import StrEnum


class ListSubmittalStatusesResponse200ItemStatus(StrEnum):
    CLOSED = "Closed"
    DRAFT = "Draft"
    OPEN = "Open"

    def __str__(self) -> str:
        return str(self.value)
