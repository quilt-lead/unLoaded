from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_custom_fields_custom_field_custom_field_boolean_definition_id import (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldBooleanDefinitionId,
    )
    from ..models.procore_change_event_custom_fields_custom_field_custom_field_decimal_definition_id import (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldDecimalDefinitionId,
    )
    from ..models.procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id import (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId,
    )
    from ..models.procore_change_event_custom_fields_custom_field_custom_field_lov_entry_definition_id import (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntryDefinitionId,
    )
    from ..models.procore_change_event_custom_fields_custom_field_custom_field_string_definition_id import (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId,
    )


T = TypeVar("T", bound="ProcoreChangeEventCustomFields")


@_attrs_define
class ProcoreChangeEventCustomFields:
    """
    Attributes:
        custom_field_custom_field_boolean_definition_id
            (ProcoreChangeEventCustomFieldsCustomFieldCustomFieldBooleanDefinitionId | Unset):
        custom_field_custom_field_decimal_definition_id
            (ProcoreChangeEventCustomFieldsCustomFieldCustomFieldDecimalDefinitionId | Unset):
        custom_field_custom_field_lov_entries_definition_id
            (ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId | Unset):
        custom_field_custom_field_lov_entry_definition_id
            (ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntryDefinitionId | Unset):
        custom_field_custom_field_string_definition_id
            (ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId | Unset):
    """

    custom_field_custom_field_boolean_definition_id: (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldBooleanDefinitionId | Unset
    ) = UNSET
    custom_field_custom_field_decimal_definition_id: (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldDecimalDefinitionId | Unset
    ) = UNSET
    custom_field_custom_field_lov_entries_definition_id: (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId
        | Unset
    ) = UNSET
    custom_field_custom_field_lov_entry_definition_id: (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntryDefinitionId | Unset
    ) = UNSET
    custom_field_custom_field_string_definition_id: (
        ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        custom_field_custom_field_boolean_definition_id: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_field_custom_field_boolean_definition_id, Unset):
            custom_field_custom_field_boolean_definition_id = (
                self.custom_field_custom_field_boolean_definition_id.to_dict()
            )

        custom_field_custom_field_decimal_definition_id: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_field_custom_field_decimal_definition_id, Unset):
            custom_field_custom_field_decimal_definition_id = (
                self.custom_field_custom_field_decimal_definition_id.to_dict()
            )

        custom_field_custom_field_lov_entries_definition_id: dict[str, Any] | Unset = (
            UNSET
        )
        if not isinstance(
            self.custom_field_custom_field_lov_entries_definition_id, Unset
        ):
            custom_field_custom_field_lov_entries_definition_id = (
                self.custom_field_custom_field_lov_entries_definition_id.to_dict()
            )

        custom_field_custom_field_lov_entry_definition_id: dict[str, Any] | Unset = (
            UNSET
        )
        if not isinstance(
            self.custom_field_custom_field_lov_entry_definition_id, Unset
        ):
            custom_field_custom_field_lov_entry_definition_id = (
                self.custom_field_custom_field_lov_entry_definition_id.to_dict()
            )

        custom_field_custom_field_string_definition_id: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_field_custom_field_string_definition_id, Unset):
            custom_field_custom_field_string_definition_id = (
                self.custom_field_custom_field_string_definition_id.to_dict()
            )

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if custom_field_custom_field_boolean_definition_id is not UNSET:
            field_dict["custom_field_%{custom_field_boolean_definition_id}"] = (
                custom_field_custom_field_boolean_definition_id
            )
        if custom_field_custom_field_decimal_definition_id is not UNSET:
            field_dict["custom_field_%{custom_field_decimal_definition_id}"] = (
                custom_field_custom_field_decimal_definition_id
            )
        if custom_field_custom_field_lov_entries_definition_id is not UNSET:
            field_dict["custom_field_%{custom_field_lov_entries_definition_id}"] = (
                custom_field_custom_field_lov_entries_definition_id
            )
        if custom_field_custom_field_lov_entry_definition_id is not UNSET:
            field_dict["custom_field_%{custom_field_lov_entry_definition_id}"] = (
                custom_field_custom_field_lov_entry_definition_id
            )
        if custom_field_custom_field_string_definition_id is not UNSET:
            field_dict["custom_field_%{custom_field_string_definition_id}"] = (
                custom_field_custom_field_string_definition_id
            )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_custom_fields_custom_field_custom_field_boolean_definition_id import (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldBooleanDefinitionId,
        )
        from ..models.procore_change_event_custom_fields_custom_field_custom_field_decimal_definition_id import (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldDecimalDefinitionId,
        )
        from ..models.procore_change_event_custom_fields_custom_field_custom_field_lov_entries_definition_id import (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId,
        )
        from ..models.procore_change_event_custom_fields_custom_field_custom_field_lov_entry_definition_id import (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntryDefinitionId,
        )
        from ..models.procore_change_event_custom_fields_custom_field_custom_field_string_definition_id import (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId,
        )

        d = dict(src_dict)
        _custom_field_custom_field_boolean_definition_id = d.pop(
            "custom_field_%{custom_field_boolean_definition_id}", UNSET
        )
        custom_field_custom_field_boolean_definition_id: (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldBooleanDefinitionId
            | Unset
        )
        if isinstance(_custom_field_custom_field_boolean_definition_id, Unset):
            custom_field_custom_field_boolean_definition_id = UNSET
        else:
            custom_field_custom_field_boolean_definition_id = ProcoreChangeEventCustomFieldsCustomFieldCustomFieldBooleanDefinitionId.from_dict(
                _custom_field_custom_field_boolean_definition_id
            )

        _custom_field_custom_field_decimal_definition_id = d.pop(
            "custom_field_%{custom_field_decimal_definition_id}", UNSET
        )
        custom_field_custom_field_decimal_definition_id: (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldDecimalDefinitionId
            | Unset
        )
        if isinstance(_custom_field_custom_field_decimal_definition_id, Unset):
            custom_field_custom_field_decimal_definition_id = UNSET
        else:
            custom_field_custom_field_decimal_definition_id = ProcoreChangeEventCustomFieldsCustomFieldCustomFieldDecimalDefinitionId.from_dict(
                _custom_field_custom_field_decimal_definition_id
            )

        _custom_field_custom_field_lov_entries_definition_id = d.pop(
            "custom_field_%{custom_field_lov_entries_definition_id}", UNSET
        )
        custom_field_custom_field_lov_entries_definition_id: (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId
            | Unset
        )
        if isinstance(_custom_field_custom_field_lov_entries_definition_id, Unset):
            custom_field_custom_field_lov_entries_definition_id = UNSET
        else:
            custom_field_custom_field_lov_entries_definition_id = ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntriesDefinitionId.from_dict(
                _custom_field_custom_field_lov_entries_definition_id
            )

        _custom_field_custom_field_lov_entry_definition_id = d.pop(
            "custom_field_%{custom_field_lov_entry_definition_id}", UNSET
        )
        custom_field_custom_field_lov_entry_definition_id: (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntryDefinitionId
            | Unset
        )
        if isinstance(_custom_field_custom_field_lov_entry_definition_id, Unset):
            custom_field_custom_field_lov_entry_definition_id = UNSET
        else:
            custom_field_custom_field_lov_entry_definition_id = ProcoreChangeEventCustomFieldsCustomFieldCustomFieldLovEntryDefinitionId.from_dict(
                _custom_field_custom_field_lov_entry_definition_id
            )

        _custom_field_custom_field_string_definition_id = d.pop(
            "custom_field_%{custom_field_string_definition_id}", UNSET
        )
        custom_field_custom_field_string_definition_id: (
            ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId
            | Unset
        )
        if isinstance(_custom_field_custom_field_string_definition_id, Unset):
            custom_field_custom_field_string_definition_id = UNSET
        else:
            custom_field_custom_field_string_definition_id = ProcoreChangeEventCustomFieldsCustomFieldCustomFieldStringDefinitionId.from_dict(
                _custom_field_custom_field_string_definition_id
            )

        procore_change_event_custom_fields = cls(
            custom_field_custom_field_boolean_definition_id=custom_field_custom_field_boolean_definition_id,
            custom_field_custom_field_decimal_definition_id=custom_field_custom_field_decimal_definition_id,
            custom_field_custom_field_lov_entries_definition_id=custom_field_custom_field_lov_entries_definition_id,
            custom_field_custom_field_lov_entry_definition_id=custom_field_custom_field_lov_entry_definition_id,
            custom_field_custom_field_string_definition_id=custom_field_custom_field_string_definition_id,
        )

        procore_change_event_custom_fields.additional_properties = d
        return procore_change_event_custom_fields

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
