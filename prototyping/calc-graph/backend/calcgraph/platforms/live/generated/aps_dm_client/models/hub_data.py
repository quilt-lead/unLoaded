from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.type_hub import TypeHub
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.hub_data_attributes import HubDataAttributes
    from ..models.hub_data_relationships import HubDataRelationships
    from ..models.json_api_links_self import JsonApiLinksSelf


T = TypeVar("T", bound="HubData")


@_attrs_define
class HubData:
    """The object containing information about the hub.

    Attributes:
        links (JsonApiLinksSelf): An object containing the URI of the endpoint to access this resource.
        attributes (HubDataAttributes | Unset): The properties of the hub.
        id (str | Unset): The hub ID, which uniquely identifies the hub.
        relationships (HubDataRelationships | Unset): Contains links to resources that are directly related to this hub.
        type_ (TypeHub | Unset): The type of the resource. Possible values are ``hubs``.
    """

    links: JsonApiLinksSelf
    attributes: HubDataAttributes | Unset = UNSET
    id: str | Unset = UNSET
    relationships: HubDataRelationships | Unset = UNSET
    type_: TypeHub | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        links = self.links.to_dict()

        attributes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.attributes, Unset):
            attributes = self.attributes.to_dict()

        id = self.id

        relationships: dict[str, Any] | Unset = UNSET
        if not isinstance(self.relationships, Unset):
            relationships = self.relationships.to_dict()

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "links": links,
            }
        )
        if attributes is not UNSET:
            field_dict["attributes"] = attributes
        if id is not UNSET:
            field_dict["id"] = id
        if relationships is not UNSET:
            field_dict["relationships"] = relationships
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.hub_data_attributes import HubDataAttributes
        from ..models.hub_data_relationships import HubDataRelationships
        from ..models.json_api_links_self import JsonApiLinksSelf

        d = dict(src_dict)
        links = JsonApiLinksSelf.from_dict(d.pop("links"))

        _attributes = d.pop("attributes", UNSET)
        attributes: HubDataAttributes | Unset
        if isinstance(_attributes, Unset):
            attributes = UNSET
        else:
            attributes = HubDataAttributes.from_dict(_attributes)

        id = d.pop("id", UNSET)

        _relationships = d.pop("relationships", UNSET)
        relationships: HubDataRelationships | Unset
        if isinstance(_relationships, Unset):
            relationships = UNSET
        else:
            relationships = HubDataRelationships.from_dict(_relationships)

        _type_ = d.pop("type", UNSET)
        type_: TypeHub | Unset
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = TypeHub(_type_)

        hub_data = cls(
            links=links,
            attributes=attributes,
            id=id,
            relationships=relationships,
            type_=type_,
        )

        hub_data.additional_properties = d
        return hub_data

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
