from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventResponse201ChangeType")


@_attrs_define
class CreateChangeEventResponse201ChangeType:
    """
    Attributes:
        abbreviation (str | Unset): abbreviation
        id (int | Unset): ID
        name (str | Unset): name
    """

    abbreviation: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        abbreviation = self.abbreviation

        id = self.id

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if abbreviation is not UNSET:
            field_dict["abbreviation"] = abbreviation
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        abbreviation = d.pop("abbreviation", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        create_change_event_response_201_change_type = cls(
            abbreviation=abbreviation,
            id=id,
            name=name,
        )

        create_change_event_response_201_change_type.additional_properties = d
        return create_change_event_response_201_change_type

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
