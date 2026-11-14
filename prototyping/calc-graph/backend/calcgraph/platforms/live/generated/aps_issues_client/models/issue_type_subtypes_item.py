from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssueTypeSubtypesItem")


@_attrs_define
class IssueTypeSubtypesItem:
    """
    Attributes:
        code (str | Unset): 3 chars pin label.
        created_at (str | Unset): The date and time the issue was created, in ISO8601 format.
        created_by (str | Unset): The unique identifier of the user who created the issue type.
        deleted_at (str | Unset): The date and time the issue type was deleted, in ISO8601 format.
        deleted_by (str | Unset): The unique identifier of the user who deleted the issue type.
        id (str | Unset): The ID of the issue subtype.
        is_active (bool | Unset): States whether the issue type is active.
        is_read_only (bool | Unset): Not relevant
        issue_type_id (str | Unset): The ID of the parent issue type.
        order_index (int | Unset): Not relevant
        permitted_actions (list[str] | Unset): Not relevant
        permitted_attributes (list[str] | Unset): Not relevant
        title (str | Unset): Max length: 250
        updated_at (str | Unset): The date and time the issue type was updated, in ISO8601 format.
        updated_by (str | Unset): The unique identifier of the user who updated the issue type.
    """

    code: str | Unset = UNSET
    created_at: str | Unset = UNSET
    created_by: str | Unset = UNSET
    deleted_at: str | Unset = UNSET
    deleted_by: str | Unset = UNSET
    id: str | Unset = UNSET
    is_active: bool | Unset = UNSET
    is_read_only: bool | Unset = UNSET
    issue_type_id: str | Unset = UNSET
    order_index: int | Unset = UNSET
    permitted_actions: list[str] | Unset = UNSET
    permitted_attributes: list[str] | Unset = UNSET
    title: str | Unset = UNSET
    updated_at: str | Unset = UNSET
    updated_by: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        created_at = self.created_at

        created_by = self.created_by

        deleted_at = self.deleted_at

        deleted_by = self.deleted_by

        id = self.id

        is_active = self.is_active

        is_read_only = self.is_read_only

        issue_type_id = self.issue_type_id

        order_index = self.order_index

        permitted_actions: list[str] | Unset = UNSET
        if not isinstance(self.permitted_actions, Unset):
            permitted_actions = self.permitted_actions

        permitted_attributes: list[str] | Unset = UNSET
        if not isinstance(self.permitted_attributes, Unset):
            permitted_attributes = self.permitted_attributes

        title = self.title

        updated_at = self.updated_at

        updated_by = self.updated_by

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if code is not UNSET:
            field_dict["code"] = code
        if created_at is not UNSET:
            field_dict["createdAt"] = created_at
        if created_by is not UNSET:
            field_dict["createdBy"] = created_by
        if deleted_at is not UNSET:
            field_dict["deletedAt"] = deleted_at
        if deleted_by is not UNSET:
            field_dict["deletedBy"] = deleted_by
        if id is not UNSET:
            field_dict["id"] = id
        if is_active is not UNSET:
            field_dict["isActive"] = is_active
        if is_read_only is not UNSET:
            field_dict["isReadOnly"] = is_read_only
        if issue_type_id is not UNSET:
            field_dict["issueTypeId"] = issue_type_id
        if order_index is not UNSET:
            field_dict["orderIndex"] = order_index
        if permitted_actions is not UNSET:
            field_dict["permittedActions"] = permitted_actions
        if permitted_attributes is not UNSET:
            field_dict["permittedAttributes"] = permitted_attributes
        if title is not UNSET:
            field_dict["title"] = title
        if updated_at is not UNSET:
            field_dict["updatedAt"] = updated_at
        if updated_by is not UNSET:
            field_dict["updatedBy"] = updated_by

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        code = d.pop("code", UNSET)

        created_at = d.pop("createdAt", UNSET)

        created_by = d.pop("createdBy", UNSET)

        deleted_at = d.pop("deletedAt", UNSET)

        deleted_by = d.pop("deletedBy", UNSET)

        id = d.pop("id", UNSET)

        is_active = d.pop("isActive", UNSET)

        is_read_only = d.pop("isReadOnly", UNSET)

        issue_type_id = d.pop("issueTypeId", UNSET)

        order_index = d.pop("orderIndex", UNSET)

        permitted_actions = cast(list[str], d.pop("permittedActions", UNSET))

        permitted_attributes = cast(list[str], d.pop("permittedAttributes", UNSET))

        title = d.pop("title", UNSET)

        updated_at = d.pop("updatedAt", UNSET)

        updated_by = d.pop("updatedBy", UNSET)

        issue_type_subtypes_item = cls(
            code=code,
            created_at=created_at,
            created_by=created_by,
            deleted_at=deleted_at,
            deleted_by=deleted_by,
            id=id,
            is_active=is_active,
            is_read_only=is_read_only,
            issue_type_id=issue_type_id,
            order_index=order_index,
            permitted_actions=permitted_actions,
            permitted_attributes=permitted_attributes,
            title=title,
            updated_at=updated_at,
            updated_by=updated_by,
        )

        issue_type_subtypes_item.additional_properties = d
        return issue_type_subtypes_item

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
