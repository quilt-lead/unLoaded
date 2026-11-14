from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_submittal_statuses_response_200_item_status import (
    ListSubmittalStatusesResponse200ItemStatus,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="ListSubmittalStatusesResponse200Item")


@_attrs_define
class ListSubmittalStatusesResponse200Item:
    """
    Attributes:
        id (int | Unset): Unique identifier for this submittal status.
        is_default (bool | Unset): Whether this is a company default submittal status.
        name (str | Unset): Display name of the submittal status.
        status (ListSubmittalStatusesResponse200ItemStatus | Unset): Lifecycle category of the submittal status.
    """

    id: int | Unset = UNSET
    is_default: bool | Unset = UNSET
    name: str | Unset = UNSET
    status: ListSubmittalStatusesResponse200ItemStatus | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        is_default = self.is_default

        name = self.name

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if is_default is not UNSET:
            field_dict["is_default"] = is_default
        if name is not UNSET:
            field_dict["name"] = name
        if status is not UNSET:
            field_dict["status"] = status

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        is_default = d.pop("is_default", UNSET)

        name = d.pop("name", UNSET)

        _status = d.pop("status", UNSET)
        status: ListSubmittalStatusesResponse200ItemStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ListSubmittalStatusesResponse200ItemStatus(_status)

        list_submittal_statuses_response_200_item = cls(
            id=id,
            is_default=is_default,
            name=name,
            status=status,
        )

        list_submittal_statuses_response_200_item.additional_properties = d
        return list_submittal_statuses_response_200_item

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
