from enum import StrEnum


class GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItemSegmentType(
    StrEnum
):
    ATTRIBUTE = "attribute"
    COST_CODE = "cost_code"
    CUSTOM = "custom"
    LINE_ITEM_TYPE = "line_item_type"
    SUB_JOB = "sub_job"

    def __str__(self) -> str:
        return str(self.value)
