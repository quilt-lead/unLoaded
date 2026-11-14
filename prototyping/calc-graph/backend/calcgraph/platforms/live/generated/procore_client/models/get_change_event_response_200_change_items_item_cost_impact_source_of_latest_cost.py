from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemCostImpactSourceOfLatestCost(StrEnum):
    COMMITMENT = "commitment"
    ESTIMATE = "estimate"
    LATEST_QUOTE = "latest_quote"
    NON_COMMITMENT = "non_commitment"

    def __str__(self) -> str:
        return str(self.value)
