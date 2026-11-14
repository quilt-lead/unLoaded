from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListCompaniesResponse200Item")


@_attrs_define
class ListCompaniesResponse200Item:
    """Company visible to the current user.

    Attributes:
        id (int | Unset): Unique identifier for the company.
        is_active (bool | Unset): Whether the company is active.
        logo_url (str | Unset): URL of the company logo.
        my_company (bool | None | Unset): Whether the current user is an active employee of this company. True for at
            most one company in a list response.
        name (str | Unset): Display name of the company.
        pcn_business_experience (bool | None | Unset): Whether Procore Construction Network business experience is
            enabled for the company.
    """

    id: int | Unset = UNSET
    is_active: bool | Unset = UNSET
    logo_url: str | Unset = UNSET
    my_company: bool | None | Unset = UNSET
    name: str | Unset = UNSET
    pcn_business_experience: bool | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        is_active = self.is_active

        logo_url = self.logo_url

        my_company: bool | None | Unset
        if isinstance(self.my_company, Unset):
            my_company = UNSET
        else:
            my_company = self.my_company

        name = self.name

        pcn_business_experience: bool | None | Unset
        if isinstance(self.pcn_business_experience, Unset):
            pcn_business_experience = UNSET
        else:
            pcn_business_experience = self.pcn_business_experience

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if is_active is not UNSET:
            field_dict["is_active"] = is_active
        if logo_url is not UNSET:
            field_dict["logo_url"] = logo_url
        if my_company is not UNSET:
            field_dict["my_company"] = my_company
        if name is not UNSET:
            field_dict["name"] = name
        if pcn_business_experience is not UNSET:
            field_dict["pcn_business_experience"] = pcn_business_experience

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        is_active = d.pop("is_active", UNSET)

        logo_url = d.pop("logo_url", UNSET)

        def _parse_my_company(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        my_company = _parse_my_company(d.pop("my_company", UNSET))

        name = d.pop("name", UNSET)

        def _parse_pcn_business_experience(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        pcn_business_experience = _parse_pcn_business_experience(
            d.pop("pcn_business_experience", UNSET)
        )

        list_companies_response_200_item = cls(
            id=id,
            is_active=is_active,
            logo_url=logo_url,
            my_company=my_company,
            name=name,
            pcn_business_experience=pcn_business_experience,
        )

        list_companies_response_200_item.additional_properties = d
        return list_companies_response_200_item

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
