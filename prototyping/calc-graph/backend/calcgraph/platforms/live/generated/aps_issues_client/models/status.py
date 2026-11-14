from enum import StrEnum


class Status(StrEnum):
    CLOSED = "closed"
    COMPLETED = "completed"
    DRAFT = "draft"
    IN_DISPUTE = "in_dispute"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    NOT_APPROVED = "not_approved"
    OPEN = "open"
    PENDING = "pending"

    def __str__(self) -> str:
        return str(self.value)
