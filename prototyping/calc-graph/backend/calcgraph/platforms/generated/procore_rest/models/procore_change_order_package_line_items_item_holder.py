from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreChangeOrderPackageLineItemsItemHolder")


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemHolder:
    """Holder

    Attributes:
        holder_type (str | Unset): Holder type
        id (int | Unset): ID
    """

    holder_type: str | Unset = UNSET
    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        holder_type = self.holder_type

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if holder_type is not UNSET:
            field_dict["holder_type"] = holder_type
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        holder_type = d.pop("holder_type", UNSET)

        id = d.pop("id", UNSET)

        procore_change_order_package_line_items_item_holder = cls(
            holder_type=holder_type,
            id=id,
        )

        procore_change_order_package_line_items_item_holder.additional_properties = d
        return procore_change_order_package_line_items_item_holder

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
