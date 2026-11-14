from enum import StrEnum


class ProcoreChangeEventChangeItemsItemBudgetImpactSourceOfBudgetRom(StrEnum):
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    QUANTITY_BY_UNIT_COST = "quantity_by_unit_cost"

    def __str__(self) -> str:
        return str(self.value)
