from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="IssuePermittedActions")


@_attrs_define
class IssuePermittedActions:
    """The list of actions permitted for the user for this issue in its current state.
    Note that if a user with Create for my company permissions attempts to assign a user from a another company to the
    issue, it will return an error.

    Possible Values: assign_all (can assign another user from another company to the issue), assign_same_company (can
    only assign another user from the same company to the issue), clear_assignee, delete, add_comment, add_attachment,
    remove_attachment.

    The following values are not relevant: add_attachment, remove_attachment.

    """

    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        issue_permitted_actions = cls()

        issue_permitted_actions.additional_properties = d
        return issue_permitted_actions

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
