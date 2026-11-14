from enum import StrEnum


class ProcoreChangeEventChangeItemsItemCostImpactRequestForQuoteType0Status(StrEnum):
    CLOSED = "closed"
    OUT_FOR_PRICING = "out_for_pricing"
    PENDING_FINAL_APPROVAL = "pending_final_approval"
    REVISE_AND_RESUBMIT = "revise_and_resubmit"
    UNDER_REVIEW = "under_review"
    WITHDRAWN = "withdrawn"

    def __str__(self) -> str:
        return str(self.value)
