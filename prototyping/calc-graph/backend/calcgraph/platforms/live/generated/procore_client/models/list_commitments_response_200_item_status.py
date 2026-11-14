from enum import StrEnum


class ListCommitmentsResponse200ItemStatus(StrEnum):
    APPROVED = "Approved"
    COMPLETE = "Complete"
    DRAFT = "Draft"
    OUT_FOR_BID = "Out For Bid"
    OUT_FOR_SIGNATURE = "Out For Signature"
    TERMINATED = "Terminated"
    VOID = "Void"

    def __str__(self) -> str:
        return str(self.value)
