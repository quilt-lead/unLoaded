from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventResponse201ExternalData")


@_attrs_define
class CreateChangeEventResponse201ExternalData:
    """
    Attributes:
        origin_data (None | str | Unset): The Origin Data of the Change Event
        origin_id (None | str | Unset): The Origin ID of the Change Event
    """

    origin_data: None | str | Unset = UNSET
    origin_id: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        origin_data: None | str | Unset
        if isinstance(self.origin_data, Unset):
            origin_data = UNSET
        else:
            origin_data = self.origin_data

        origin_id: None | str | Unset
        if isinstance(self.origin_id, Unset):
            origin_id = UNSET
        else:
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

        def _parse_origin_data(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_data = _parse_origin_data(d.pop("origin_data", UNSET))

        def _parse_origin_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_id = _parse_origin_id(d.pop("origin_id", UNSET))

        create_change_event_response_201_external_data = cls(
            origin_data=origin_data,
            origin_id=origin_id,
        )

        create_change_event_response_201_external_data.additional_properties = d
        return create_change_event_response_201_external_data

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
