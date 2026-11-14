from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.project_extension_with_schema_link import (
        ProjectExtensionWithSchemaLink,
    )


T = TypeVar("T", bound="ProjectDataAttributes")


@_attrs_define
class ProjectDataAttributes:
    """The properties of the project.

    Attributes:
        extension (ProjectExtensionWithSchemaLink | Unset): A container of additional properties that extends the
            default properties of this resource.
        name (str | Unset): A human friendly name to identify the project.
        scopes (list[str] | Unset): The array of scopes that apply to this project.
    """

    extension: ProjectExtensionWithSchemaLink | Unset = UNSET
    name: str | Unset = UNSET
    scopes: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        extension: dict[str, Any] | Unset = UNSET
        if not isinstance(self.extension, Unset):
            extension = self.extension.to_dict()

        name = self.name

        scopes: list[str] | Unset = UNSET
        if not isinstance(self.scopes, Unset):
            scopes = self.scopes

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if extension is not UNSET:
            field_dict["extension"] = extension
        if name is not UNSET:
            field_dict["name"] = name
        if scopes is not UNSET:
            field_dict["scopes"] = scopes

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.project_extension_with_schema_link import (
            ProjectExtensionWithSchemaLink,
        )

        d = dict(src_dict)
        _extension = d.pop("extension", UNSET)
        extension: ProjectExtensionWithSchemaLink | Unset
        if isinstance(_extension, Unset):
            extension = UNSET
        else:
            extension = ProjectExtensionWithSchemaLink.from_dict(_extension)

        name = d.pop("name", UNSET)

        scopes = cast(list[str], d.pop("scopes", UNSET))

        project_data_attributes = cls(
            extension=extension,
            name=name,
            scopes=scopes,
        )

        project_data_attributes.additional_properties = d
        return project_data_attributes

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
