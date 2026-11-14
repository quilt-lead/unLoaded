from enum import StrEnum


class ListRfisSerializerView(StrEnum):
    BASE_WEB_INDEX = "base_web_index"
    FLATTEN_V0 = "flatten_v0"
    IDS_ONLY = "ids_only"
    WEB_INDEX = "web_index"

    def __str__(self) -> str:
        return str(self.value)
