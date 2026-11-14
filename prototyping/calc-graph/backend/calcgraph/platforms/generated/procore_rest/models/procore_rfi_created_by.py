from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_rfi_created_by_vendor_type_0 import (
        ProcoreRfiCreatedByVendorType0,
    )


T = TypeVar("T", bound="ProcoreRfiCreatedBy")


@_attrs_define
class ProcoreRfiCreatedBy:
    """User who created the RFI.

    Attributes:
        id (int): Unique identifier for the user's login information.
        login (str): User email address.
        name (str): User's first and last name without their company name.
        locale (None | str | Unset): User locale.
        vendor (None | ProcoreRfiCreatedByVendorType0 | Unset): Company associated with the creator, or null when the
            creator has no company.
    """

    id: int
    login: str
    name: str
    locale: None | str | Unset = UNSET
    vendor: None | ProcoreRfiCreatedByVendorType0 | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.procore_rfi_created_by_vendor_type_0 import (
            ProcoreRfiCreatedByVendorType0,
        )

        id = self.id

        login = self.login

        name = self.name

        locale: None | str | Unset
        if isinstance(self.locale, Unset):
            locale = UNSET
        else:
            locale = self.locale

        vendor: dict[str, Any] | None | Unset
        if isinstance(self.vendor, Unset):
            vendor = UNSET
        elif isinstance(self.vendor, ProcoreRfiCreatedByVendorType0):
            vendor = self.vendor.to_dict()
        else:
            vendor = self.vendor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "id": id,
                "login": login,
                "name": name,
            }
        )
        if locale is not UNSET:
            field_dict["locale"] = locale
        if vendor is not UNSET:
            field_dict["vendor"] = vendor

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_rfi_created_by_vendor_type_0 import (
            ProcoreRfiCreatedByVendorType0,
        )

        d = dict(src_dict)
        id = d.pop("id")

        login = d.pop("login")

        name = d.pop("name")

        def _parse_locale(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        locale = _parse_locale(d.pop("locale", UNSET))

        def _parse_vendor(
            data: object,
        ) -> None | ProcoreRfiCreatedByVendorType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                vendor_type_0 = ProcoreRfiCreatedByVendorType0.from_dict(data)

                return vendor_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ProcoreRfiCreatedByVendorType0 | Unset, data)

        vendor = _parse_vendor(d.pop("vendor", UNSET))

        procore_rfi_created_by = cls(
            id=id,
            login=login,
            name=name,
            locale=locale,
            vendor=vendor,
        )

        procore_rfi_created_by.additional_properties = d
        return procore_rfi_created_by

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
