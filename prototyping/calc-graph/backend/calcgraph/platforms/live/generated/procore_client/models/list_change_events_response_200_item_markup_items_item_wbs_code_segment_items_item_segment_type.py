from enum import StrEnum


class ListChangeEventsResponse200ItemMarkupItemsItemWbsCodeSegmentItemsItemSegmentType(
    StrEnum
):
    ATTRIBUTE = "attribute"
    COST_CODE = "cost_code"
    CUSTOM = "custom"
    LINE_ITEM_TYPE = "line_item_type"
    SUB_JOB = "sub_job"

    def __str__(self) -> str:
        return str(self.value)
