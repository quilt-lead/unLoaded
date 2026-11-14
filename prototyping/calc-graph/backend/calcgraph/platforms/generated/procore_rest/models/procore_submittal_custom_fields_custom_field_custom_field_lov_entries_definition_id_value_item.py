from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ProcoreSubmittalCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem",
)


@_attrs_define
class ProcoreSubmittalCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem:
    """
    Attributes:
        id (int | Unset): The unique identifier of the list of values (LOV) entry.
        label (str | Unset): The label of the list of values (LOV) entry.
    """

    id: int | Unset = UNSET
    label: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        label = self.label

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if label is not UNSET:
            field_dict["label"] = label

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        label = d.pop("label", UNSET)

        procore_submittal_custom_fields_custom_field_custom_field_lov_entries_definition_id_value_item = cls(
            id=id,
            label=label,
        )

        procore_submittal_custom_fields_custom_field_custom_field_lov_entries_definition_id_value_item.additional_properties = d
        return procore_submittal_custom_fields_custom_field_custom_field_lov_entries_definition_id_value_item

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
