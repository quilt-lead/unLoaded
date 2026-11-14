from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.hub_data import HubData
    from ..models.json_api_links_self import JsonApiLinksSelf
    from ..models.json_api_version import JsonApiVersion


T = TypeVar("T", bound="HubsResponse")


@_attrs_define
class HubsResponse:
    """Successful retrieval of the hubs collection.

    Attributes:
        data (list[HubData] | Unset): An array of objects where each object represents a hub.
        jsonapi (JsonApiVersion | Unset): The JSON API object.
        links (JsonApiLinksSelf | Unset): An object containing the URI of the endpoint to access this resource.
    """

    data: list[HubData] | Unset = UNSET
    jsonapi: JsonApiVersion | Unset = UNSET
    links: JsonApiLinksSelf | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.data, Unset):
            data = []
            for data_item_data in self.data:
                data_item = data_item_data.to_dict()
                data.append(data_item)

        jsonapi: dict[str, Any] | Unset = UNSET
        if not isinstance(self.jsonapi, Unset):
            jsonapi = self.jsonapi.to_dict()

        links: dict[str, Any] | Unset = UNSET
        if not isinstance(self.links, Unset):
            links = self.links.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if data is not UNSET:
            field_dict["data"] = data
        if jsonapi is not UNSET:
            field_dict["jsonapi"] = jsonapi
        if links is not UNSET:
            field_dict["links"] = links

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.hub_data import HubData
        from ..models.json_api_links_self import JsonApiLinksSelf
        from ..models.json_api_version import JsonApiVersion

        d = dict(src_dict)
        _data = d.pop("data", UNSET)
        data: list[HubData] | Unset = UNSET
        if _data is not UNSET:
            data = []
            for data_item_data in _data:
                data_item = HubData.from_dict(data_item_data)

                data.append(data_item)

        _jsonapi = d.pop("jsonapi", UNSET)
        jsonapi: JsonApiVersion | Unset
        if isinstance(_jsonapi, Unset):
            jsonapi = UNSET
        else:
            jsonapi = JsonApiVersion.from_dict(_jsonapi)

        _links = d.pop("links", UNSET)
        links: JsonApiLinksSelf | Unset
        if isinstance(_links, Unset):
            links = UNSET
        else:
            links = JsonApiLinksSelf.from_dict(_links)

        hubs_response = cls(
            data=data,
            jsonapi=jsonapi,
            links=links,
        )

        hubs_response.additional_properties = d
        return hubs_response

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
