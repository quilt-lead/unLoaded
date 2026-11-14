from enum import StrEnum


class CreateSubmittalBodySubmittalLeadTimeFormat(StrEnum):
    DAYS = "days"
    WEEKS = "weeks"

    def __str__(self) -> str:
        return str(self.value)
