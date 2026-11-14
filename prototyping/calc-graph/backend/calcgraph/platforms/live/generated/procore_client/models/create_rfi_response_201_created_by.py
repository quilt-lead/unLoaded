from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_rfi_response_201_created_by_vendor_type_0 import (
        CreateRfiResponse201CreatedByVendorType0,
    )


T = TypeVar("T", bound="CreateRfiResponse201CreatedBy")


@_attrs_define
class CreateRfiResponse201CreatedBy:
    """User who created the RFI.

    Attributes:
        id (int): Unique identifier for the user's login information.
        login (str): User email address.
        name (str): User's first and last name without their company name.
        locale (None | str | Unset): User locale.
        vendor (CreateRfiResponse201CreatedByVendorType0 | None | Unset): Company associated with the creator, or null
            when the creator has no company.
    """

    id: int
    login: str
    name: str
    locale: None | str | Unset = UNSET
    vendor: CreateRfiResponse201CreatedByVendorType0 | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_rfi_response_201_created_by_vendor_type_0 import (
            CreateRfiResponse201CreatedByVendorType0,
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
        elif isinstance(self.vendor, CreateRfiResponse201CreatedByVendorType0):
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
        from ..models.create_rfi_response_201_created_by_vendor_type_0 import (
            CreateRfiResponse201CreatedByVendorType0,
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
        ) -> CreateRfiResponse201CreatedByVendorType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                vendor_type_0 = CreateRfiResponse201CreatedByVendorType0.from_dict(data)

                return vendor_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201CreatedByVendorType0 | None | Unset, data)

        vendor = _parse_vendor(d.pop("vendor", UNSET))

        create_rfi_response_201_created_by = cls(
            id=id,
            login=login,
            name=name,
            locale=locale,
            vendor=vendor,
        )

        create_rfi_response_201_created_by.additional_properties = d
        return create_rfi_response_201_created_by

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
