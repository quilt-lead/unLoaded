from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.json_api_meta_link import JsonApiMetaLink
    from ..models.json_api_type_id import JsonApiTypeId


T = TypeVar("T", bound="JsonApiRelationshipsLinksOnlyBim")


@_attrs_define
class JsonApiRelationshipsLinksOnlyBim:
    """Contains links to resources that are external to the data domain service. This is available only with BIM360.

    Attributes:
        data (JsonApiTypeId): An object containing the ``id`` and ``type`` properties of a resource.
        meta (JsonApiMetaLink): Meta-information on links to this resource.
    """

    data: JsonApiTypeId
    meta: JsonApiMetaLink
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = self.data.to_dict()

        meta = self.meta.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "data": data,
                "meta": meta,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_meta_link import JsonApiMetaLink
        from ..models.json_api_type_id import JsonApiTypeId

        d = dict(src_dict)
        data = JsonApiTypeId.from_dict(d.pop("data"))

        meta = JsonApiMetaLink.from_dict(d.pop("meta"))

        json_api_relationships_links_only_bim = cls(
            data=data,
            meta=meta,
        )

        json_api_relationships_links_only_bim.additional_properties = d
        return json_api_relationships_links_only_bim

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
