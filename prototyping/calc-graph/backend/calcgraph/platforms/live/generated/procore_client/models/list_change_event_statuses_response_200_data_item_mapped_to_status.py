from enum import StrEnum


class ListChangeEventStatusesResponse200DataItemMappedToStatus(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    PENDING = "pending"
    VOID = "void"

    def __str__(self) -> str:
        return str(self.value)
