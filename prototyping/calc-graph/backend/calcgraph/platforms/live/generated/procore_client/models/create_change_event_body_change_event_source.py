from enum import StrEnum


class CreateChangeEventBodyChangeEventSource(StrEnum):
    BUDGET_CHANGE = "budget_change"
    FIELD_INITIATED_CHANGE_ORDERS = "field_initiated_change_orders"

    def __str__(self) -> str:
        return str(self.value)
