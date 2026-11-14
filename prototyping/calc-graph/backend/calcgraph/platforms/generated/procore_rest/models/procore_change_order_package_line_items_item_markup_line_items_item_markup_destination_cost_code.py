from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode",
)


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode:
    """
    Attributes:
        origin_data (str | Unset): Cost Code third party data
        origin_id (str | Unset): Cost Code third party id
    """

    origin_data: str | Unset = UNSET
    origin_id: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        origin_data = self.origin_data

        origin_id = self.origin_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if origin_data is not UNSET:
            field_dict["origin_data"] = origin_data
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        origin_data = d.pop("origin_data", UNSET)

        origin_id = d.pop("origin_id", UNSET)

        procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_cost_code = cls(
            origin_data=origin_data,
            origin_id=origin_id,
        )

        procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_cost_code.additional_properties = d
        return procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_cost_code

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
