from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemRevenueImpactSourceOfRevenueRom(StrEnum):
    AUTOMATIC = "automatic"
    LATEST_COST = "latest_cost"
    MANUAL = "manual"
    NO_REVENUE_EXPECTED = "no_revenue_expected"

    def __str__(self) -> str:
        return str(self.value)
