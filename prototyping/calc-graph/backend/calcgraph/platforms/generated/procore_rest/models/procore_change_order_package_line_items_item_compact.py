from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreChangeOrderPackageLineItemsItemCompact")


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemCompact:
    """
    Attributes:
        full_code (str | Unset): Full Cost code, including parent prefixes
        id (int | None | Unset): ID
        name (str | Unset): Name
    """

    full_code: str | Unset = UNSET
    id: int | None | Unset = UNSET
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        full_code = self.full_code

        id: int | None | Unset
        if isinstance(self.id, Unset):
            id = UNSET
        else:
            id = self.id

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if full_code is not UNSET:
            field_dict["full_code"] = full_code
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        full_code = d.pop("full_code", UNSET)

        def _parse_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        id = _parse_id(d.pop("id", UNSET))

        name = d.pop("name", UNSET)

        procore_change_order_package_line_items_item_compact = cls(
            full_code=full_code,
            id=id,
            name=name,
        )

        procore_change_order_package_line_items_item_compact.additional_properties = d
        return procore_change_order_package_line_items_item_compact

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
