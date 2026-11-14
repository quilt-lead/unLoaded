from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ProcoreChangeEventChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem",
)


@_attrs_define
class ProcoreChangeEventChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem:
    """
    Attributes:
        amount (str | Unset): Sum of all Adjustment Line Item amounts under same adjustment number
        id (int | Unset): Adjustment Line Item ID
        number (int | Unset): Number of this adjustment
    """

    amount: str | Unset = UNSET
    id: int | Unset = UNSET
    number: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        id = self.id

        number = self.number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        id = d.pop("id", UNSET)

        number = d.pop("number", UNSET)

        procore_change_event_change_items_item_budget_impact_budget_change_adjustment_line_item = cls(
            amount=amount,
            id=id,
            number=number,
        )

        procore_change_event_change_items_item_budget_impact_budget_change_adjustment_line_item.additional_properties = d
        return procore_change_event_change_items_item_budget_impact_budget_change_adjustment_line_item

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
