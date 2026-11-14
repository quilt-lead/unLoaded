from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issue_type_subtypes_item import IssueTypeSubtypesItem


T = TypeVar("T", bound="IssueType")


@_attrs_define
class IssueType:
    """
    Attributes:
        container_id (str | Unset): Not relevant
        created_at (str | Unset): The date and time the issue was created, in ISO8601 format.
        created_by (str | Unset): The unique identifier of the user who created the issue type.
        deleted_at (str | Unset): The date and time the issue type was deleted, in ISO8601 format.
        deleted_by (str | Unset): The unique identifier of the user who deleted the issue type.
        id (str | Unset): The ID of the issue type.
        is_active (bool | Unset): States whether the issue type is active.
        order_index (int | Unset): Not relevant
        permitted_actions (list[str] | Unset): Not relevant
        permitted_attributes (list[str] | Unset): Not relevant
        status_set (str | Unset): Not relevant
        subtypes (list[IssueTypeSubtypesItem] | Unset): A list of subtypes of the specific issue type.
        title (str | Unset): Max length: 250
        updated_at (str | Unset): The date and time the issue type was updated, in ISO8601 format.
        updated_by (str | Unset): The unique identifier of the user who updated the issue type.
    """

    container_id: str | Unset = UNSET
    created_at: str | Unset = UNSET
    created_by: str | Unset = UNSET
    deleted_at: str | Unset = UNSET
    deleted_by: str | Unset = UNSET
    id: str | Unset = UNSET
    is_active: bool | Unset = UNSET
    order_index: int | Unset = UNSET
    permitted_actions: list[str] | Unset = UNSET
    permitted_attributes: list[str] | Unset = UNSET
    status_set: str | Unset = UNSET
    subtypes: list[IssueTypeSubtypesItem] | Unset = UNSET
    title: str | Unset = UNSET
    updated_at: str | Unset = UNSET
    updated_by: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        container_id = self.container_id

        created_at = self.created_at

        created_by = self.created_by

        deleted_at = self.deleted_at

        deleted_by = self.deleted_by

        id = self.id

        is_active = self.is_active

        order_index = self.order_index

        permitted_actions: list[str] | Unset = UNSET
        if not isinstance(self.permitted_actions, Unset):
            permitted_actions = self.permitted_actions

        permitted_attributes: list[str] | Unset = UNSET
        if not isinstance(self.permitted_attributes, Unset):
            permitted_attributes = self.permitted_attributes

        status_set = self.status_set

        subtypes: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.subtypes, Unset):
            subtypes = []
            for subtypes_item_data in self.subtypes:
                subtypes_item = subtypes_item_data.to_dict()
                subtypes.append(subtypes_item)

        title = self.title

        updated_at = self.updated_at

        updated_by = self.updated_by

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if container_id is not UNSET:
            field_dict["containerId"] = container_id
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
        if order_index is not UNSET:
            field_dict["orderIndex"] = order_index
        if permitted_actions is not UNSET:
            field_dict["permittedActions"] = permitted_actions
        if permitted_attributes is not UNSET:
            field_dict["permittedAttributes"] = permitted_attributes
        if status_set is not UNSET:
            field_dict["statusSet"] = status_set
        if subtypes is not UNSET:
            field_dict["subtypes"] = subtypes
        if title is not UNSET:
            field_dict["title"] = title
        if updated_at is not UNSET:
            field_dict["updatedAt"] = updated_at
        if updated_by is not UNSET:
            field_dict["updatedBy"] = updated_by

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_type_subtypes_item import IssueTypeSubtypesItem

        d = dict(src_dict)
        container_id = d.pop("containerId", UNSET)

        created_at = d.pop("createdAt", UNSET)

        created_by = d.pop("createdBy", UNSET)

        deleted_at = d.pop("deletedAt", UNSET)

        deleted_by = d.pop("deletedBy", UNSET)

        id = d.pop("id", UNSET)

        is_active = d.pop("isActive", UNSET)

        order_index = d.pop("orderIndex", UNSET)

        permitted_actions = cast(list[str], d.pop("permittedActions", UNSET))

        permitted_attributes = cast(list[str], d.pop("permittedAttributes", UNSET))

        status_set = d.pop("statusSet", UNSET)

        _subtypes = d.pop("subtypes", UNSET)
        subtypes: list[IssueTypeSubtypesItem] | Unset = UNSET
        if _subtypes is not UNSET:
            subtypes = []
            for subtypes_item_data in _subtypes:
                subtypes_item = IssueTypeSubtypesItem.from_dict(subtypes_item_data)

                subtypes.append(subtypes_item)

        title = d.pop("title", UNSET)

        updated_at = d.pop("updatedAt", UNSET)

        updated_by = d.pop("updatedBy", UNSET)

        issue_type = cls(
            container_id=container_id,
            created_at=created_at,
            created_by=created_by,
            deleted_at=deleted_at,
            deleted_by=deleted_by,
            id=id,
            is_active=is_active,
            order_index=order_index,
            permitted_actions=permitted_actions,
            permitted_attributes=permitted_attributes,
            status_set=status_set,
            subtypes=subtypes,
            title=title,
            updated_at=updated_at,
            updated_by=updated_by,
        )

        issue_type.additional_properties = d
        return issue_type

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
