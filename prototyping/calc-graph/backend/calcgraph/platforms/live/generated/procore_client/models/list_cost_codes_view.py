from enum import StrEnum


class ListCostCodesView(StrEnum):
    DEFAULT = "default"
    ERP_COMPACT = "erp_compact"

    def __str__(self) -> str:
        return str(self.value)
