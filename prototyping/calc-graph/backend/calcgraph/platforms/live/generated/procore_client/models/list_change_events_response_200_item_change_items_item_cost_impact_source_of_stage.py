from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemCostImpactSourceOfStage(StrEnum):
    CHANGE_ORDER_PACKAGE = "change_order_package"
    COMMITMENT = "commitment"
    ESTIMATE = "estimate"
    LATEST_QUOTE = "latest_quote"
    NON_COMMITMENT = "non-commitment"

    def __str__(self) -> str:
        return str(self.value)
