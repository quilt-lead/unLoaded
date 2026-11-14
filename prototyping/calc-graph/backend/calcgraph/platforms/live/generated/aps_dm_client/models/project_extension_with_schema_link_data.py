from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.project_type_bim_360_acc import ProjectTypeBim360Acc
from ..types import UNSET, Unset

T = TypeVar("T", bound="ProjectExtensionWithSchemaLinkData")


@_attrs_define
class ProjectExtensionWithSchemaLinkData:
    """The object that contains the additional properties, which makes this resource extensible.

    Attributes:
        project_type (ProjectTypeBim360Acc | Unset): The type of project. Only relevant for BIM 360 and Forma projects.
            Possible values: ``BIM360`` (for BIM 360 projects), ``ACC`` (for Forma projects).
    """

    project_type: ProjectTypeBim360Acc | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        project_type: str | Unset = UNSET
        if not isinstance(self.project_type, Unset):
            project_type = self.project_type.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if project_type is not UNSET:
            field_dict["projectType"] = project_type

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _project_type = d.pop("projectType", UNSET)
        project_type: ProjectTypeBim360Acc | Unset
        if isinstance(_project_type, Unset):
            project_type = UNSET
        else:
            project_type = ProjectTypeBim360Acc(_project_type)

        project_extension_with_schema_link_data = cls(
            project_type=project_type,
        )

        project_extension_with_schema_link_data.additional_properties = d
        return project_extension_with_schema_link_data

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
