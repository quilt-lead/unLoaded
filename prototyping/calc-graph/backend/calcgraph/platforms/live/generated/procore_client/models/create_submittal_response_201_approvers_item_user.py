from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateSubmittalResponse201ApproversItemUser")


@_attrs_define
class CreateSubmittalResponse201ApproversItemUser:
    """
    Attributes:
        id (int | Unset):
        login (str | Unset): Email
        name (str | Unset):
    """

    id: int | Unset = UNSET
    login: str | Unset = UNSET
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        login = self.login

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if login is not UNSET:
            field_dict["login"] = login
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        login = d.pop("login", UNSET)

        name = d.pop("name", UNSET)

        create_submittal_response_201_approvers_item_user = cls(
            id=id,
            login=login,
            name=name,
        )

        create_submittal_response_201_approvers_item_user.additional_properties = d
        return create_submittal_response_201_approvers_item_user

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
