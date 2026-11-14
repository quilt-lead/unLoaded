from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="UserIssuesNew")


@_attrs_define
class UserIssuesNew:
    """If this object appears in the response, it indicates that the user can create and modify issues.

    Attributes:
        permittedActions (list[str] | Unset): The list of actions permitted for the user for this issue in its current
            state.
        permittedAttributes (list[str] | Unset): A list of attributes you are allowed to open a new issue. issueTypeId,
            linkedDocument, links, ownerId, officialResponse, rootCauseId, snapshotUrn are not applicable.
        permittedStatuses (list[str] | Unset): A list of available statuses for the project.
            Possible values: draft, open, pending, in_progress, completed, in_review, not_approved, in_dispute, closed.
        permitted_actions (list[str] | Unset): Not relevant
        permitted_attributes (list[str] | Unset): Not relevant
        permitted_statuses (list[str] | Unset): Not relevant
    """

    permittedActions: list[str] | Unset = UNSET
    permittedAttributes: list[str] | Unset = UNSET
    permittedStatuses: list[str] | Unset = UNSET
    permitted_actions: list[str] | Unset = UNSET
    permitted_attributes: list[str] | Unset = UNSET
    permitted_statuses: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        permittedActions: list[str] | Unset = UNSET
        if not isinstance(self.permittedActions, Unset):
            permittedActions = self.permittedActions

        permittedAttributes: list[str] | Unset = UNSET
        if not isinstance(self.permittedAttributes, Unset):
            permittedAttributes = self.permittedAttributes

        permittedStatuses: list[str] | Unset = UNSET
        if not isinstance(self.permittedStatuses, Unset):
            permittedStatuses = self.permittedStatuses

        permitted_actions: list[str] | Unset = UNSET
        if not isinstance(self.permitted_actions, Unset):
            permitted_actions = self.permitted_actions

        permitted_attributes: list[str] | Unset = UNSET
        if not isinstance(self.permitted_attributes, Unset):
            permitted_attributes = self.permitted_attributes

        permitted_statuses: list[str] | Unset = UNSET
        if not isinstance(self.permitted_statuses, Unset):
            permitted_statuses = self.permitted_statuses

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if permittedActions is not UNSET:
            field_dict["permittedActions"] = permittedActions
        if permittedAttributes is not UNSET:
            field_dict["permittedAttributes"] = permittedAttributes
        if permittedStatuses is not UNSET:
            field_dict["permittedStatuses"] = permittedStatuses
        if permitted_actions is not UNSET:
            field_dict["permitted_actions"] = permitted_actions
        if permitted_attributes is not UNSET:
            field_dict["permitted_attributes"] = permitted_attributes
        if permitted_statuses is not UNSET:
            field_dict["permitted_statuses"] = permitted_statuses

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        permittedActions = cast(list[str], d.pop("permittedActions", UNSET))

        permittedAttributes = cast(list[str], d.pop("permittedAttributes", UNSET))

        permittedStatuses = cast(list[str], d.pop("permittedStatuses", UNSET))

        permitted_actions = cast(list[str], d.pop("permitted_actions", UNSET))

        permitted_attributes = cast(list[str], d.pop("permitted_attributes", UNSET))

        permitted_statuses = cast(list[str], d.pop("permitted_statuses", UNSET))

        user_issues_new = cls(
            permittedActions=permittedActions,
            permittedAttributes=permittedAttributes,
            permittedStatuses=permittedStatuses,
            permitted_actions=permitted_actions,
            permitted_attributes=permitted_attributes,
            permitted_statuses=permitted_statuses,
        )

        user_issues_new.additional_properties = d
        return user_issues_new

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
