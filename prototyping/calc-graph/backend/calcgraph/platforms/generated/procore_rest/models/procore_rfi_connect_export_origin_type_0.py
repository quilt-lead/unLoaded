from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreRfiConnectExportOriginType0")


@_attrs_define
class ProcoreRfiConnectExportOriginType0:
    """Export origin information for RFIs received via cross-account collaboration. Null for RFIs not received via export.

    Attributes:
        rfi_number (str | Unset): The originating RFI number. Returns "Draft" if the source RFI was a draft at export
            time.
        source_provider_name (str | Unset): The originating company name (cross-company export) or project name (same-
            company export).
    """

    rfi_number: str | Unset = UNSET
    source_provider_name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        rfi_number = self.rfi_number

        source_provider_name = self.source_provider_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if rfi_number is not UNSET:
            field_dict["rfi_number"] = rfi_number
        if source_provider_name is not UNSET:
            field_dict["source_provider_name"] = source_provider_name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        rfi_number = d.pop("rfi_number", UNSET)

        source_provider_name = d.pop("source_provider_name", UNSET)

        procore_rfi_connect_export_origin_type_0 = cls(
            rfi_number=rfi_number,
            source_provider_name=source_provider_name,
        )

        procore_rfi_connect_export_origin_type_0.additional_properties = d
        return procore_rfi_connect_export_origin_type_0

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
