from enum import StrEnum


class ListCostCodesResponse200ItemLineItemTypesItemBaseType(StrEnum):
    COMMITMENT = "commitment"
    EQUIPMENT = "equipment"
    LABOR = "labor"
    MATERIALS = "materials"
    OTHER = "other"
    OWNER_COST = "owner_cost"
    PROFESSIONAL_SERVICES = "professional_services"

    def __str__(self) -> str:
        return str(self.value)
