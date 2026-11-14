from enum import StrEnum


class ListCostCodesResponse200ItemBillerType(StrEnum):
    PROJECT = "Project"
    SUBJOB = "SubJob"
    VALUE_2 = ""

    def __str__(self) -> str:
        return str(self.value)
