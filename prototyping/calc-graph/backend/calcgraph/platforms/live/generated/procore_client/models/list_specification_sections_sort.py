from enum import StrEnum


class ListSpecificationSectionsSort(StrEnum):
    NUMBER = "number"

    def __str__(self) -> str:
        return str(self.value)
