from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateRfiResponse201CustomTextfield2Type0")


@_attrs_define
class CreateRfiResponse201CustomTextfield2Type0:
    """Custom RFI text field 2

    Attributes:
        label (str | Unset): Project label for RFI custom text field 2
        value (str | Unset): Value for RFI custom text field 2
    """

    label: str | Unset = UNSET
    value: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        label = self.label

        value = self.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if label is not UNSET:
            field_dict["label"] = label
        if value is not UNSET:
            field_dict["value"] = value

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        label = d.pop("label", UNSET)

        value = d.pop("value", UNSET)

        create_rfi_response_201_custom_textfield_2_type_0 = cls(
            label=label,
            value=value,
        )

        create_rfi_response_201_custom_textfield_2_type_0.additional_properties = d
        return create_rfi_response_201_custom_textfield_2_type_0

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
