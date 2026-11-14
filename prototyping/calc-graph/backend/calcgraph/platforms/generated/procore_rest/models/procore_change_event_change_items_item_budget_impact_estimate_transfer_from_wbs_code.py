from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code_segment_items_item import (
        ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItem,
    )


T = TypeVar(
    "T",
    bound="ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode",
)


@_attrs_define
class ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode:
    """Item's associated Budget Code

    Attributes:
        description (str | Unset): wbs code description
        flat_code (str | Unset): wbs code flat code
        id (int | Unset): ID
        segment_items (list[ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItem] |
            Unset): Work breakdown structure segment items
    """

    description: str | Unset = UNSET
    flat_code: str | Unset = UNSET
    id: int | Unset = UNSET
    segment_items: (
        list[
            ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItem
        ]
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        flat_code = self.flat_code

        id = self.id

        segment_items: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.segment_items, Unset):
            segment_items = []
            for segment_items_item_data in self.segment_items:
                segment_items_item = segment_items_item_data.to_dict()
                segment_items.append(segment_items_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if description is not UNSET:
            field_dict["description"] = description
        if flat_code is not UNSET:
            field_dict["flat_code"] = flat_code
        if id is not UNSET:
            field_dict["id"] = id
        if segment_items is not UNSET:
            field_dict["segment_items"] = segment_items

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code_segment_items_item import (
            ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItem,
        )

        d = dict(src_dict)
        description = d.pop("description", UNSET)

        flat_code = d.pop("flat_code", UNSET)

        id = d.pop("id", UNSET)

        _segment_items = d.pop("segment_items", UNSET)
        segment_items: (
            list[
                ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItem
            ]
            | Unset
        ) = UNSET
        if _segment_items is not UNSET:
            segment_items = []
            for segment_items_item_data in _segment_items:
                segment_items_item = ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCodeSegmentItemsItem.from_dict(
                    segment_items_item_data
                )

                segment_items.append(segment_items_item)

        procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code = cls(
            description=description,
            flat_code=flat_code,
            id=id,
            segment_items=segment_items,
        )

        procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code.additional_properties = d
        return procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code

    @property
    def additional_keys(self) -> list[str]:
        return list(self.additional_properties.keys())

    def __getitem__(self, key: str) -> Any:
        return self.additional_properties[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self.additional_properties[key] = value

    def __delitem__(self, key: str) -> None:
        del self.additional_properties[key]

    def __contains__(self, key: str) -> bool:
        return key in self.additional_properties
