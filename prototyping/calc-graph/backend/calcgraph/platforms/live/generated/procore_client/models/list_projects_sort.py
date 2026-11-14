from enum import StrEnum


class ListProjectsSort(StrEnum):
    DISPLAY_NAME = "display_name"
    NAME = "name"
    PROJECT_NUMBER = "project_number"
    STATUS = "status"

    def __str__(self) -> str:
        return str(self.value)
