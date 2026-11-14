from enum import StrEnum


class ProcoreCostCodeBillerType(StrEnum):
    PROJECT = "Project"
    SUBJOB = "SubJob"

    def __str__(self) -> str:
        return str(self.value)
