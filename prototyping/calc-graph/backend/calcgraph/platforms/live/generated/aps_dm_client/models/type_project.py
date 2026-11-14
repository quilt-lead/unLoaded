from enum import StrEnum


class TypeProject(StrEnum):
    PROJECTS = "projects"

    def __str__(self) -> str:
        return str(self.value)
