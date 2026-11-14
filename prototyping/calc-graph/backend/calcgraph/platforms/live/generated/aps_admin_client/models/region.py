from enum import StrEnum


class Region(StrEnum):
    AUS = "AUS"
    CAN = "CAN"
    DEU = "DEU"
    EMEA = "EMEA"
    GBR = "GBR"
    IND = "IND"
    JPN = "JPN"
    US = "US"

    def __str__(self) -> str:
        return str(self.value)
