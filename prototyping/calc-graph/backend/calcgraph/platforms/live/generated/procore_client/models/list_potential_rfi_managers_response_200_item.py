from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListPotentialRfiManagersResponse200Item")


@_attrs_define
class ListPotentialRfiManagersResponse200Item:
    """
    Attributes:
        id (int | Unset): Unique integer identifier for this user.
        locale (None | str | Unset): Locale preference of the user, e.g. `en-US`. Null if not explicitly set.
        login (str | Unset): Email address (login) of the user. Uniquely identifies the account across Procore.
        name (str | Unset): Full display name of the user, formatted as first + last name.
    """

    id: int | Unset = UNSET
    locale: None | str | Unset = UNSET
    login: str | Unset = UNSET
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        locale: None | str | Unset
        if isinstance(self.locale, Unset):
            locale = UNSET
        else:
            locale = self.locale

        login = self.login

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if locale is not UNSET:
            field_dict["locale"] = locale
        if login is not UNSET:
            field_dict["login"] = login
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        def _parse_locale(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        locale = _parse_locale(d.pop("locale", UNSET))

        login = d.pop("login", UNSET)

        name = d.pop("name", UNSET)

        list_potential_rfi_managers_response_200_item = cls(
            id=id,
            locale=locale,
            login=login,
            name=name,
        )

        list_potential_rfi_managers_response_200_item.additional_properties = d
        return list_potential_rfi_managers_response_200_item

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
