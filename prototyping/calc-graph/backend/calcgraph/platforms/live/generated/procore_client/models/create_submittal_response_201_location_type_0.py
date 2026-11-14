from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateSubmittalResponse201LocationType0")


@_attrs_define
class CreateSubmittalResponse201LocationType0:
    """
    Attributes:
        created_at (datetime.datetime | Unset): Timestamp of Location creation
        id (int | Unset): Location ID
        name (str | Unset): Location name
        node_name (str | Unset): Location node name
        parent_id (int | Unset): Location parent id
        updated_at (datetime.datetime | Unset): Timestamp of last update to Location
    """

    created_at: datetime.datetime | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    node_name: str | Unset = UNSET
    parent_id: int | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        id = self.id

        name = self.name

        node_name = self.node_name

        parent_id = self.parent_id

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if node_name is not UNSET:
            field_dict["node_name"] = node_name
        if parent_id is not UNSET:
            field_dict["parent_id"] = parent_id
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        node_name = d.pop("node_name", UNSET)

        parent_id = d.pop("parent_id", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        create_submittal_response_201_location_type_0 = cls(
            created_at=created_at,
            id=id,
            name=name,
            node_name=node_name,
            parent_id=parent_id,
            updated_at=updated_at,
        )

        create_submittal_response_201_location_type_0.additional_properties = d
        return create_submittal_response_201_location_type_0

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
