from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.create_change_event_body_change_event import (
        CreateChangeEventBodyChangeEvent,
    )


T = TypeVar("T", bound="CreateChangeEventBody")


@_attrs_define
class CreateChangeEventBody:
    """
    Attributes:
        change_event (CreateChangeEventBodyChangeEvent):
    """

    change_event: CreateChangeEventBodyChangeEvent
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        change_event = self.change_event.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "change_event": change_event,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_body_change_event import (
            CreateChangeEventBodyChangeEvent,
        )

        d = dict(src_dict)
        change_event = CreateChangeEventBodyChangeEvent.from_dict(d.pop("change_event"))

        create_change_event_body = cls(
            change_event=change_event,
        )

        create_change_event_body.additional_properties = d
        return create_change_event_body

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
