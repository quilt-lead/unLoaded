from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssueLinkedDocumentsItemDetailsPosition")


@_attrs_define
class IssueLinkedDocumentsItemDetailsPosition:
    """The position of the pushpin in the viewable.

    Attributes:
        x (float | Unset): The x-value of the position in the viewable.
        y (float | Unset): The y-value of the position in the viewable.
        z (float | Unset): The z-value of the position in the viewable.
    """

    x: float | Unset = UNSET
    y: float | Unset = UNSET
    z: float | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        x = self.x

        y = self.y

        z = self.z

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if x is not UNSET:
            field_dict["x"] = x
        if y is not UNSET:
            field_dict["y"] = y
        if z is not UNSET:
            field_dict["z"] = z

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        x = d.pop("x", UNSET)

        y = d.pop("y", UNSET)

        z = d.pop("z", UNSET)

        issue_linked_documents_item_details_position = cls(
            x=x,
            y=y,
            z=z,
        )

        issue_linked_documents_item_details_position.additional_properties = d
        return issue_linked_documents_item_details_position

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
