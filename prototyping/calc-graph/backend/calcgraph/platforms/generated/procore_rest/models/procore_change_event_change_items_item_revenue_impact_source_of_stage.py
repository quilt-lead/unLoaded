from enum import StrEnum


class ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfStage(StrEnum):
    CHANGE_ORDER = "change_order"
    CHANGE_ORDER_PACKAGE = "change_order_package"
    ESTIMATE = "estimate"

    def __str__(self) -> str:
        return str(self.value)
