from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId"
)


@_attrs_define
class ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId:
    """
    Attributes:
        data_type (str | Unset): Data type of the Custom Field Definition
        value (str | Unset): The value of the custom field
        variant (str | Unset): The variant of the Custom Field Definition (e.g. `phone_number`). Present only when the
            definition has an associated variant.
    """

    data_type: str | Unset = UNSET
    value: str | Unset = UNSET
    variant: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data_type = self.data_type

        value = self.value

        variant = self.variant

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if data_type is not UNSET:
            field_dict["data_type"] = data_type
        if value is not UNSET:
            field_dict["value"] = value
        if variant is not UNSET:
            field_dict["variant"] = variant

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        data_type = d.pop("data_type", UNSET)

        value = d.pop("value", UNSET)

        variant = d.pop("variant", UNSET)

        procore_change_event_custom_fields_custom_field_custom_field_string_definition_id = cls(
            data_type=data_type,
            value=value,
            variant=variant,
        )

        procore_change_event_custom_fields_custom_field_custom_field_string_definition_id.additional_properties = d
        return procore_change_event_custom_fields_custom_field_custom_field_string_definition_id

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
