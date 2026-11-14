from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_cost_codes_response_200_item_line_item_types_item_base_type import (
    ListCostCodesResponse200ItemLineItemTypesItemBaseType,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="ListCostCodesResponse200ItemLineItemTypesItem")


@_attrs_define
class ListCostCodesResponse200ItemLineItemTypesItem:
    """A line item type assigned to this cost code.

    Attributes:
        base_type (ListCostCodesResponse200ItemLineItemTypesItemBaseType | Unset): Canonical cost category for this line
            item type. One of: 'equipment', 'materials', 'commitment', 'owner_cost', 'professional_services', 'labor',
            'other'.
        code (str | Unset): Short code used for CSV import of this Line Item Type.
        id (int | Unset): Unique identifier for the Line Item Type.
        name (str | Unset): Display name of the Line Item Type.
        origin_id (None | str | Unset): ERP system identifier for this line item type. Null when not linked to an ERP
            system.
    """

    base_type: ListCostCodesResponse200ItemLineItemTypesItemBaseType | Unset = UNSET
    code: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    origin_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base_type: str | Unset = UNSET
        if not isinstance(self.base_type, Unset):
            base_type = self.base_type.value

        code = self.code

        id = self.id

        name = self.name

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
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _base_type = d.pop("base_type", UNSET)
        base_type: ListCostCodesResponse200ItemLineItemTypesItemBaseType | Unset
        if isinstance(_base_type, Unset):
            base_type = UNSET
        else:
            base_type = ListCostCodesResponse200ItemLineItemTypesItemBaseType(
                _base_type
            )

        code = d.pop("code", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        def _parse_origin_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_id = _parse_origin_id(d.pop("origin_id", UNSET))

        list_cost_codes_response_200_item_line_item_types_item = cls(
            base_type=base_type,
            code=code,
            id=id,
            name=name,
            origin_id=origin_id,
        )

        list_cost_codes_response_200_item_line_item_types_item.additional_properties = d
        return list_cost_codes_response_200_item_line_item_types_item

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
