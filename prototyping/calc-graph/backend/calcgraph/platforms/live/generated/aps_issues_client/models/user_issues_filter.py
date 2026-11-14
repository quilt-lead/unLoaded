from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="UserIssuesFilter")


@_attrs_define
class UserIssuesFilter:
    """Not relevant

    Attributes:
        permitted_statuses (list[str] | Unset): Not relevant
    """

    permitted_statuses: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        permitted_statuses: list[str] | Unset = UNSET
        if not isinstance(self.permitted_statuses, Unset):
            permitted_statuses = self.permitted_statuses

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if permitted_statuses is not UNSET:
            field_dict["permittedStatuses"] = permitted_statuses

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        permitted_statuses = cast(list[str], d.pop("permittedStatuses", UNSET))

        user_issues_filter = cls(
            permitted_statuses=permitted_statuses,
        )

        user_issues_filter.additional_properties = d
        return user_issues_filter

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
