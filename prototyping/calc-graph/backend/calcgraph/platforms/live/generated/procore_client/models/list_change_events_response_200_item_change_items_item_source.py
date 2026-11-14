from enum import StrEnum


class ListChangeEventsResponse200ItemChangeItemsItemSource(StrEnum):
    BUDGET_CHANGE = "budget_change"
    CHANGE_EVENT = "change_event"
    FIELD_INITIATED_CHANGE_ORDERS = "field_initiated_change_orders"

    def __str__(self) -> str:
        return str(self.value)
