from enum import StrEnum


class AssignedToType(StrEnum):
    COMPANY = "company"
    ROLE = "role"
    USER = "user"

    def __str__(self) -> str:
        return str(self.value)
