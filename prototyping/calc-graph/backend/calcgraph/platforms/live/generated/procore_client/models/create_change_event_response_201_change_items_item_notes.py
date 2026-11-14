from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="CreateChangeEventResponse201ChangeItemsItemNotes")


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemNotes:
    """After successful update independent actions may be executed. For example: sync WBS code. The failures of those
    actions will be aggregated under attribute :notes and will not result in a Failure.

    """

    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        create_change_event_response_201_change_items_item_notes = cls()

        create_change_event_response_201_change_items_item_notes.additional_properties = d
        return create_change_event_response_201_change_items_item_notes

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
