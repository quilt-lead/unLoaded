from enum import StrEnum


class CreateRfiResponse201Status(StrEnum):
    CLOSED = "closed"
    CLOSED_DRAFT = "closed_draft"
    CLOSED_WITH_REVISION = "closed_with_revision"
    DRAFT = "draft"
    OPEN = "open"

    def __str__(self) -> str:
        return str(self.value)
