from enum import StrEnum


class ProcoreChangeEventChangeItemsItemCostImpactCommitmentType0Type(StrEnum):
    CHANGE_ORDER_PACKAGE = "change_order_package"
    CONTRACT = "contract"
    POTENTIAL_CHANGE_ORDER = "potential_change_order"

    def __str__(self) -> str:
        return str(self.value)
