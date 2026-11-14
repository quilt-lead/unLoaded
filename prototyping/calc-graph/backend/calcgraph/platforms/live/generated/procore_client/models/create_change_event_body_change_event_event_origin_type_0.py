from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_body_change_event_event_origin_type_0_origin_type import (
    CreateChangeEventBodyChangeEventEventOriginType0OriginType,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventBodyChangeEventEventOriginType0")


@_attrs_define
class CreateChangeEventBodyChangeEventEventOriginType0:
    """
    Attributes:
        origin_id (int | Unset): ID of related event origin
        origin_type (CreateChangeEventBodyChangeEventEventOriginType0OriginType | Unset): type of related event origin
    """

    origin_id: int | Unset = UNSET
    origin_type: CreateChangeEventBodyChangeEventEventOriginType0OriginType | Unset = (
        UNSET
    )
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        origin_id = self.origin_id

        origin_type: str | Unset = UNSET
        if not isinstance(self.origin_type, Unset):
            origin_type = self.origin_type.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id
        if origin_type is not UNSET:
            field_dict["origin_type"] = origin_type

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        origin_id = d.pop("origin_id", UNSET)

        _origin_type = d.pop("origin_type", UNSET)
        origin_type: CreateChangeEventBodyChangeEventEventOriginType0OriginType | Unset
        if isinstance(_origin_type, Unset):
            origin_type = UNSET
        else:
            origin_type = CreateChangeEventBodyChangeEventEventOriginType0OriginType(
                _origin_type
            )

        create_change_event_body_change_event_event_origin_type_0 = cls(
            origin_id=origin_id,
            origin_type=origin_type,
        )

        create_change_event_body_change_event_event_origin_type_0.additional_properties = d
        return create_change_event_body_change_event_event_origin_type_0

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
