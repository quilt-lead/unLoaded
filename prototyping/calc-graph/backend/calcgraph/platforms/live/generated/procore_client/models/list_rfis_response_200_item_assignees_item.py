from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListRfisResponse200ItemAssigneesItem")


@_attrs_define
class ListRfisResponse200ItemAssigneesItem:
    """
    Attributes:
        id (int | Unset):
        locale (str | Unset): User locale
        login (str | Unset): Email
        name (str | Unset):
        response_required (bool | Unset): Designate whether or not the assignee is required to respond
    """

    id: int | Unset = UNSET
    locale: str | Unset = UNSET
    login: str | Unset = UNSET
    name: str | Unset = UNSET
    response_required: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        locale = self.locale

        login = self.login

        name = self.name

        response_required = self.response_required

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
        if response_required is not UNSET:
            field_dict["response_required"] = response_required

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        locale = d.pop("locale", UNSET)

        login = d.pop("login", UNSET)

        name = d.pop("name", UNSET)

        response_required = d.pop("response_required", UNSET)

        list_rfis_response_200_item_assignees_item = cls(
            id=id,
            locale=locale,
            login=login,
            name=name,
            response_required=response_required,
        )

        list_rfis_response_200_item_assignees_item.additional_properties = d
        return list_rfis_response_200_item_assignees_item

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
