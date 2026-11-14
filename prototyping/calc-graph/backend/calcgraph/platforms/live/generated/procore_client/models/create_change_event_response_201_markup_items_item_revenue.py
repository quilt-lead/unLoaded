from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventResponse201MarkupItemsItemRevenue")


@_attrs_define
class CreateChangeEventResponse201MarkupItemsItemRevenue:
    """markup item revenue summary

    Attributes:
        change_order_amount (str | Unset): prime potential change order line items amount
        estimate_amount (str | Unset): estimated amount
        latest_price_amount (str | Unset): latest price
    """

    change_order_amount: str | Unset = UNSET
    estimate_amount: str | Unset = UNSET
    latest_price_amount: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        change_order_amount = self.change_order_amount

        estimate_amount = self.estimate_amount

        latest_price_amount = self.latest_price_amount

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if change_order_amount is not UNSET:
            field_dict["change_order_amount"] = change_order_amount
        if estimate_amount is not UNSET:
            field_dict["estimate_amount"] = estimate_amount
        if latest_price_amount is not UNSET:
            field_dict["latest_price_amount"] = latest_price_amount

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        change_order_amount = d.pop("change_order_amount", UNSET)

        estimate_amount = d.pop("estimate_amount", UNSET)

        latest_price_amount = d.pop("latest_price_amount", UNSET)

        create_change_event_response_201_markup_items_item_revenue = cls(
            change_order_amount=change_order_amount,
            estimate_amount=estimate_amount,
            latest_price_amount=latest_price_amount,
        )

        create_change_event_response_201_markup_items_item_revenue.additional_properties = d
        return create_change_event_response_201_markup_items_item_revenue

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
