from enum import StrEnum


class ListChangeOrderPackagesResponse200ItemStatus(StrEnum):
    APPROVED = "approved"
    DRAFT = "draft"
    NOT_PRICING = "not_pricing"
    NOT_PROCEEDING = "not_proceeding"
    NO_CHARGE = "no_charge"
    PENDING = "pending"
    PENDING_BILLABLE = "pending_billable"
    PRICING = "pricing"
    PROCEEDING = "proceeding"
    REJECTED = "rejected"
    REVISED = "revised"
    VOID = "void"

    def __str__(self) -> str:
        return str(self.value)
