from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.type_project import TypeProject
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_links_self_and_web_view import JsonApiLinksSelfAndWebView
    from ..models.project_data_attributes import ProjectDataAttributes
    from ..models.project_data_relationships import ProjectDataRelationships


T = TypeVar("T", bound="ProjectData")


@_attrs_define
class ProjectData:
    """A container of data describing a project.

    Attributes:
        attributes (ProjectDataAttributes): The properties of the project.
        id (str): The ID that uniquely identifies the project.
        type_ (TypeProject): The type of the resource. Possible values are ``projects``.
        links (JsonApiLinksSelfAndWebView | Unset): Information on links to this resource.
        relationships (ProjectDataRelationships | Unset): Contains links to resources related to this project.
    """

    attributes: ProjectDataAttributes
    id: str
    type_: TypeProject
    links: JsonApiLinksSelfAndWebView | Unset = UNSET
    relationships: ProjectDataRelationships | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attributes = self.attributes.to_dict()

        id = self.id

        type_ = self.type_.value

        links: dict[str, Any] | Unset = UNSET
        if not isinstance(self.links, Unset):
            links = self.links.to_dict()

        relationships: dict[str, Any] | Unset = UNSET
        if not isinstance(self.relationships, Unset):
            relationships = self.relationships.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "attributes": attributes,
                "id": id,
                "type": type_,
            }
        )
        if links is not UNSET:
            field_dict["links"] = links
        if relationships is not UNSET:
            field_dict["relationships"] = relationships

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_links_self_and_web_view import JsonApiLinksSelfAndWebView
        from ..models.project_data_attributes import ProjectDataAttributes
        from ..models.project_data_relationships import ProjectDataRelationships

        d = dict(src_dict)
        attributes = ProjectDataAttributes.from_dict(d.pop("attributes"))

        id = d.pop("id")

        type_ = TypeProject(d.pop("type"))

        _links = d.pop("links", UNSET)
        links: JsonApiLinksSelfAndWebView | Unset
        if isinstance(_links, Unset):
            links = UNSET
        else:
            links = JsonApiLinksSelfAndWebView.from_dict(_links)

        _relationships = d.pop("relationships", UNSET)
        relationships: ProjectDataRelationships | Unset
        if isinstance(_relationships, Unset):
            relationships = UNSET
        else:
            relationships = ProjectDataRelationships.from_dict(_relationships)

        project_data = cls(
            attributes=attributes,
            id=id,
            type_=type_,
            links=links,
            relationships=relationships,
        )

        project_data.additional_properties = d
        return project_data

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
