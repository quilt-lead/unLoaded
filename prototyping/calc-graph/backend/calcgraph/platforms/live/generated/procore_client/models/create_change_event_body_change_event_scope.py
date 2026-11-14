from enum import StrEnum


class CreateChangeEventBodyChangeEventScope(StrEnum):
    IN_SCOPE = "in_scope"
    OUT_OF_SCOPE = "out_of_scope"
    TBD = "tbd"

    def __str__(self) -> str:
        return str(self.value)
