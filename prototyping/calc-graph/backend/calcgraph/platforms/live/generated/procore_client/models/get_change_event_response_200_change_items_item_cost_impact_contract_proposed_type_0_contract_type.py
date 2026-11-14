from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemCostImpactContractProposedType0ContractType(
    StrEnum
):
    PURCHASE_ORDER_CONTRACT = "purchase_order_contract"
    WORK_ORDER_CONTRACT = "work_order_contract"

    def __str__(self) -> str:
        return str(self.value)
