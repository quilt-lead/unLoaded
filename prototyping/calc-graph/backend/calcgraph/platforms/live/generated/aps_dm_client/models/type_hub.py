from enum import StrEnum


class TypeHub(StrEnum):
    HUBS = "hubs"

    def __str__(self) -> str:
        return str(self.value)
