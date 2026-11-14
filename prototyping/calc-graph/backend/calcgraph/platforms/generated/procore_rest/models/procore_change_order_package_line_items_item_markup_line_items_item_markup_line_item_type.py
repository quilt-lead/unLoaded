from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_line_item_type_base_type import (
    ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemTypeBaseType,
)
from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType",
)


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType:
    """Line Item Type

    Attributes:
        base_type (ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemTypeBaseType | Unset): Base
            type
        code (str | Unset): Code for the Line Item Type
        id (int | Unset): Unique identifier for the Line Item Type
        name (str | Unset): Name for the Line Item Type
        origin_data (str | Unset): Origin data
        origin_id (None | str | Unset): Origin ID
    """

    base_type: (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemTypeBaseType
        | Unset
    ) = UNSET
    code: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    origin_data: str | Unset = UNSET
    origin_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base_type: str | Unset = UNSET
        if not isinstance(self.base_type, Unset):
            base_type = self.base_type.value

        code = self.code

        id = self.id

        name = self.name

        origin_data = self.origin_data

        origin_id: None | str | Unset
        if isinstance(self.origin_id, Unset):
            origin_id = UNSET
        else:
            origin_id = self.origin_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if base_type is not UNSET:
            field_dict["base_type"] = base_type
        if code is not UNSET:
            field_dict["code"] = code
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if origin_data is not UNSET:
            field_dict["origin_data"] = origin_data
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _base_type = d.pop("base_type", UNSET)
        base_type: (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemTypeBaseType
            | Unset
        )
        if isinstance(_base_type, Unset):
            base_type = UNSET
        else:
            base_type = ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemTypeBaseType(
                _base_type
            )

        code = d.pop("code", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        origin_data = d.pop("origin_data", UNSET)

        def _parse_origin_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_id = _parse_origin_id(d.pop("origin_id", UNSET))

        procore_change_order_package_line_items_item_markup_line_items_item_markup_line_item_type = cls(
            base_type=base_type,
            code=code,
            id=id,
            name=name,
            origin_data=origin_data,
            origin_id=origin_id,
        )

        procore_change_order_package_line_items_item_markup_line_items_item_markup_line_item_type.additional_properties = d
        return procore_change_order_package_line_items_item_markup_line_items_item_markup_line_item_type

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
