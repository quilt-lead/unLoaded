from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="GetChangeEventResponse200ChangeReason")


@_attrs_define
class GetChangeEventResponse200ChangeReason:
    """
    Attributes:
        change_reason (str | Unset): The reason for a change
        id (int | Unset): ID
    """

    change_reason: str | Unset = UNSET
    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        change_reason = self.change_reason

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if change_reason is not UNSET:
            field_dict["change_reason"] = change_reason
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        change_reason = d.pop("change_reason", UNSET)

        id = d.pop("id", UNSET)

        get_change_event_response_200_change_reason = cls(
            change_reason=change_reason,
            id=id,
        )

        get_change_event_response_200_change_reason.additional_properties = d
        return get_change_event_response_200_change_reason

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
