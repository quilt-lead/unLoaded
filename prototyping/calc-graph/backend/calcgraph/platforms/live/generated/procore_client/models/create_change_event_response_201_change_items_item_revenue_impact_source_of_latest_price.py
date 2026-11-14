from enum import StrEnum


class CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfLatestPrice(
    StrEnum
):
    CHANGE_ORDER = "change_order"
    ESTIMATE = "estimate"

    def __str__(self) -> str:
        return str(self.value)
