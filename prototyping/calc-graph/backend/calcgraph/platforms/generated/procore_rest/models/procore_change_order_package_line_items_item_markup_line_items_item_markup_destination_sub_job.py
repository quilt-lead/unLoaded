from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob",
)


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob:
    """
    Attributes:
        code (str | Unset): Unique code in the scope of a Project
        created_at (str | Unset): Created at
        id (int | Unset): ID
        name (str | Unset): Name
        origin_data (str | Unset): The Third-party Data of the Sub Job
        origin_id (str | Unset): The Third-party ID of the Sub Job
        updated_at (str | Unset): Updated at
    """

    code: str | Unset = UNSET
    created_at: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    origin_data: str | Unset = UNSET
    origin_id: str | Unset = UNSET
    updated_at: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        created_at = self.created_at

        id = self.id

        name = self.name

        origin_data = self.origin_data

        origin_id = self.origin_id

        updated_at = self.updated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if code is not UNSET:
            field_dict["code"] = code
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if origin_data is not UNSET:
            field_dict["origin_data"] = origin_data
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        code = d.pop("code", UNSET)

        created_at = d.pop("created_at", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        origin_data = d.pop("origin_data", UNSET)

        origin_id = d.pop("origin_id", UNSET)

        updated_at = d.pop("updated_at", UNSET)

        procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_sub_job = cls(
            code=code,
            created_at=created_at,
            id=id,
            name=name,
            origin_data=origin_data,
            origin_id=origin_id,
            updated_at=updated_at,
        )

        procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_sub_job.additional_properties = d
        return procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_sub_job

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
