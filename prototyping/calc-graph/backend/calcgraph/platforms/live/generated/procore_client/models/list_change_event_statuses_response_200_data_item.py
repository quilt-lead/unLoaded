from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_change_event_statuses_response_200_data_item_mapped_to_status import (
    ListChangeEventStatusesResponse200DataItemMappedToStatus,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="ListChangeEventStatusesResponse200DataItem")


@_attrs_define
class ListChangeEventStatusesResponse200DataItem:
    """
    Attributes:
        default (bool | Unset): Indicates whether this is a built-in default status (one of open, closed, void, or
            pending) rather than a custom company status.
        default_status (bool | Unset): Indicates whether this status is the company's default status applied to new
            change events.
        deletable (bool | Unset): Indicates whether this change event status can be deleted.
        id (str | Unset): Unique identifier of the change event status. Use as the {id} path parameter to update or
            delete the status.
        mapped_to_status (ListChangeEventStatusesResponse200DataItemMappedToStatus | Unset): Underlying canonical status
            this status maps to, which determines how it behaves in change event workflows.
        name (str | Unset): Display name of the change event status.
        show_in_select (bool | Unset): Indicates whether this status appears in the status selection dropdown.
    """

    default: bool | Unset = UNSET
    default_status: bool | Unset = UNSET
    deletable: bool | Unset = UNSET
    id: str | Unset = UNSET
    mapped_to_status: (
        ListChangeEventStatusesResponse200DataItemMappedToStatus | Unset
    ) = UNSET
    name: str | Unset = UNSET
    show_in_select: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        default = self.default

        default_status = self.default_status

        deletable = self.deletable

        id = self.id

        mapped_to_status: str | Unset = UNSET
        if not isinstance(self.mapped_to_status, Unset):
            mapped_to_status = self.mapped_to_status.value

        name = self.name

        show_in_select = self.show_in_select

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if default is not UNSET:
            field_dict["default"] = default
        if default_status is not UNSET:
            field_dict["default_status"] = default_status
        if deletable is not UNSET:
            field_dict["deletable"] = deletable
        if id is not UNSET:
            field_dict["id"] = id
        if mapped_to_status is not UNSET:
            field_dict["mapped_to_status"] = mapped_to_status
        if name is not UNSET:
            field_dict["name"] = name
        if show_in_select is not UNSET:
            field_dict["show_in_select"] = show_in_select

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        default = d.pop("default", UNSET)

        default_status = d.pop("default_status", UNSET)

        deletable = d.pop("deletable", UNSET)

        id = d.pop("id", UNSET)

        _mapped_to_status = d.pop("mapped_to_status", UNSET)
        mapped_to_status: (
            ListChangeEventStatusesResponse200DataItemMappedToStatus | Unset
        )
        if isinstance(_mapped_to_status, Unset):
            mapped_to_status = UNSET
        else:
            mapped_to_status = ListChangeEventStatusesResponse200DataItemMappedToStatus(
                _mapped_to_status
            )

        name = d.pop("name", UNSET)

        show_in_select = d.pop("show_in_select", UNSET)

        list_change_event_statuses_response_200_data_item = cls(
            default=default,
            default_status=default_status,
            deletable=deletable,
            id=id,
            mapped_to_status=mapped_to_status,
            name=name,
            show_in_select=show_in_select,
        )

        list_change_event_statuses_response_200_data_item.additional_properties = d
        return list_change_event_statuses_response_200_data_item

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
