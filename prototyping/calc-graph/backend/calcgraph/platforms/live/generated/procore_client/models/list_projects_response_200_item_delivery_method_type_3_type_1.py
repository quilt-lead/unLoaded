from enum import StrEnum


class ListProjectsResponse200ItemDeliveryMethodType3Type1(StrEnum):
    CONSTRUCTION_MANAGEMENT_AT_RISK_CMAR = "construction_management_at_risk_cmar"
    CONSTRUCTION_MANAGER_AS_AGENT_OWNERS_REP = (
        "construction_manager_as_agent_owners_rep"
    )
    DESIGN_BID_BUILD_DBB = "design_bid_build_dbb"
    DESIGN_BUILD_DB = "design_build_db"
    INDEFINITE_DELIVERY_INDEFINITE_QUANTITY_IDIQ = (
        "indefinite_delivery_indefinite_quantity_idiq"
    )
    INTEGRATED_PROJECT_DELIVERY = "integrated_project_delivery"
    MULTI_PRIME = "multi_prime"
    OTHER = "other"
    PUBLIC_PRIVATE_PARTNERSHIP_P3 = "public_private_partnership_p3"

    def __str__(self) -> str:
        return str(self.value)
