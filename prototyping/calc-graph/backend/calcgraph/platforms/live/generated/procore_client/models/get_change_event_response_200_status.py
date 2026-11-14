from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="GetChangeEventResponse200Status")


@_attrs_define
class GetChangeEventResponse200Status:
    """
    Attributes:
        id (int | Unset): ID
        mapped_to_status (str | Unset): mapped_to_status
        name (str | Unset): name
    """

    id: int | Unset = UNSET
    mapped_to_status: str | Unset = UNSET
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        mapped_to_status = self.mapped_to_status

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if mapped_to_status is not UNSET:
            field_dict["mapped_to_status"] = mapped_to_status
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        mapped_to_status = d.pop("mapped_to_status", UNSET)

        name = d.pop("name", UNSET)

        get_change_event_response_200_status = cls(
            id=id,
            mapped_to_status=mapped_to_status,
            name=name,
        )

        get_change_event_response_200_status.additional_properties = d
        return get_change_event_response_200_status

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
