from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id_value_item import (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem,
    )


T = TypeVar(
    "T",
    bound="ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId",
)


@_attrs_define
class ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId:
    """
    Attributes:
        data_type (str | Unset): Data type of the Custom Field Definition
        value (list[ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem] | Unset):
    """

    data_type: str | Unset = UNSET
    value: (
        list[
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem
        ]
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data_type = self.data_type

        value: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.value, Unset):
            value = []
            for value_item_data in self.value:
                value_item = value_item_data.to_dict()
                value.append(value_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if data_type is not UNSET:
            field_dict["data_type"] = data_type
        if value is not UNSET:
            field_dict["value"] = value

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id_value_item import (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem,
        )

        d = dict(src_dict)
        data_type = d.pop("data_type", UNSET)

        _value = d.pop("value", UNSET)
        value: (
            list[
                ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem
            ]
            | Unset
        ) = UNSET
        if _value is not UNSET:
            value = []
            for value_item_data in _value:
                value_item = ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionIdValueItem.from_dict(
                    value_item_data
                )

                value.append(value_item)

        procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id = cls(
            data_type=data_type,
            value=value,
        )

        procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id.additional_properties = d
        return procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id

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
