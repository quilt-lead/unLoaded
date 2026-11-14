from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_link import JsonApiLink
    from ..models.project_extension_with_schema_link_data import (
        ProjectExtensionWithSchemaLinkData,
    )


T = TypeVar("T", bound="ProjectExtensionWithSchemaLink")


@_attrs_define
class ProjectExtensionWithSchemaLink:
    """A container of additional properties that extends the default properties of this resource.

    Attributes:
        schema (JsonApiLink): An object containing the hyperlink to the referenced resource.
        type_ (str): The Type ID of the schema that defines the structure of the ``extension.data`` object.
        version (str): The version of the schema that applies to the ``extension.data`` object.
        data (ProjectExtensionWithSchemaLinkData | Unset): The object that contains the additional properties, which
            makes this resource extensible.
    """

    schema: JsonApiLink
    type_: str
    version: str
    data: ProjectExtensionWithSchemaLinkData | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        schema = self.schema.to_dict()

        type_ = self.type_

        version = self.version

        data: dict[str, Any] | Unset = UNSET
        if not isinstance(self.data, Unset):
            data = self.data.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "schema": schema,
                "type": type_,
                "version": version,
            }
        )
        if data is not UNSET:
            field_dict["data"] = data

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_link import JsonApiLink
        from ..models.project_extension_with_schema_link_data import (
            ProjectExtensionWithSchemaLinkData,
        )

        d = dict(src_dict)
        schema = JsonApiLink.from_dict(d.pop("schema"))

        type_ = d.pop("type")

        version = d.pop("version")

        _data = d.pop("data", UNSET)
        data: ProjectExtensionWithSchemaLinkData | Unset
        if isinstance(_data, Unset):
            data = UNSET
        else:
            data = ProjectExtensionWithSchemaLinkData.from_dict(_data)

        project_extension_with_schema_link = cls(
            schema=schema,
            type_=type_,
            version=version,
            data=data,
        )

        project_extension_with_schema_link.additional_properties = d
        return project_extension_with_schema_link

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
