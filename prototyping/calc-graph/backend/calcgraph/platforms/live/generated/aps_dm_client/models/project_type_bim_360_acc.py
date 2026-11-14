from enum import StrEnum


class ProjectTypeBim360Acc(StrEnum):
    ACC = "ACC"
    BIM360 = "BIM360"

    def __str__(self) -> str:
        return str(self.value)
