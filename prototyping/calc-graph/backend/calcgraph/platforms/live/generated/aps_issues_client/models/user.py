from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.permission_level import PermissionLevel
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.user_issues import UserIssues


T = TypeVar("T", bound="User")


@_attrs_define
class User:
    """
    Attributes:
        can_manage_templates (bool | Unset): Not relevant
        id (str | Unset): Unique identifier for the given user.
        is_project_admin (bool | Unset): States whether the current logged in user is a system admin.
        issues (UserIssues | Unset):
        permission_levels (list[PermissionLevel] | Unset): The permission level of the user. Each permission level
            corresponds to a combination of values in the response. For example, a combination of read and create in the
            response, corresponds to a Create for other companies permission level.
    """

    can_manage_templates: bool | Unset = UNSET
    id: str | Unset = UNSET
    is_project_admin: bool | Unset = UNSET
    issues: UserIssues | Unset = UNSET
    permission_levels: list[PermissionLevel] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        can_manage_templates = self.can_manage_templates

        id = self.id

        is_project_admin = self.is_project_admin

        issues: dict[str, Any] | Unset = UNSET
        if not isinstance(self.issues, Unset):
            issues = self.issues.to_dict()

        permission_levels: list[str] | Unset = UNSET
        if not isinstance(self.permission_levels, Unset):
            permission_levels = []
            for permission_levels_item_data in self.permission_levels:
                permission_levels_item = permission_levels_item_data.value
                permission_levels.append(permission_levels_item)

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if can_manage_templates is not UNSET:
            field_dict["canManageTemplates"] = can_manage_templates
        if id is not UNSET:
            field_dict["id"] = id
        if is_project_admin is not UNSET:
            field_dict["isProjectAdmin"] = is_project_admin
        if issues is not UNSET:
            field_dict["issues"] = issues
        if permission_levels is not UNSET:
            field_dict["permissionLevels"] = permission_levels

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.user_issues import UserIssues

        d = dict(src_dict)
        can_manage_templates = d.pop("canManageTemplates", UNSET)

        id = d.pop("id", UNSET)

        is_project_admin = d.pop("isProjectAdmin", UNSET)

        _issues = d.pop("issues", UNSET)
        issues: UserIssues | Unset
        if isinstance(_issues, Unset):
            issues = UNSET
        else:
            issues = UserIssues.from_dict(_issues)

        _permission_levels = d.pop("permissionLevels", UNSET)
        permission_levels: list[PermissionLevel] | Unset = UNSET
        if _permission_levels is not UNSET:
            permission_levels = []
            for permission_levels_item_data in _permission_levels:
                permission_levels_item = PermissionLevel(permission_levels_item_data)

                permission_levels.append(permission_levels_item)

        user = cls(
            can_manage_templates=can_manage_templates,
            id=id,
            is_project_admin=is_project_admin,
            issues=issues,
            permission_levels=permission_levels,
        )

        user.additional_properties = d
        return user

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
