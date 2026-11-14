from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListSubmittalsResponse200ItemSpecificationSectionType0")


@_attrs_define
class ListSubmittalsResponse200ItemSpecificationSectionType0:
    """
    Attributes:
        current_revision_id (int | Unset): Current Revision ID
        description (str | Unset): Description
        id (int | Unset): ID
        label (str | Unset): Label
        number (str | Unset): Number
    """

    current_revision_id: int | Unset = UNSET
    description: str | Unset = UNSET
    id: int | Unset = UNSET
    label: str | Unset = UNSET
    number: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        current_revision_id = self.current_revision_id

        description = self.description

        id = self.id

        label = self.label

        number = self.number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if current_revision_id is not UNSET:
            field_dict["current_revision_id"] = current_revision_id
        if description is not UNSET:
            field_dict["description"] = description
        if id is not UNSET:
            field_dict["id"] = id
        if label is not UNSET:
            field_dict["label"] = label
        if number is not UNSET:
            field_dict["number"] = number

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        current_revision_id = d.pop("current_revision_id", UNSET)

        description = d.pop("description", UNSET)

        id = d.pop("id", UNSET)

        label = d.pop("label", UNSET)

        number = d.pop("number", UNSET)

        list_submittals_response_200_item_specification_section_type_0 = cls(
            current_revision_id=current_revision_id,
            description=description,
            id=id,
            label=label,
            number=number,
        )

        list_submittals_response_200_item_specification_section_type_0.additional_properties = d
        return list_submittals_response_200_item_specification_section_type_0

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
