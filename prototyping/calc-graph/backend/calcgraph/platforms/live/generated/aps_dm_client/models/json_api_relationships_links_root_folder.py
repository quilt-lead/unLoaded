from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_meta_link import JsonApiMetaLink
    from ..models.json_api_type_id import JsonApiTypeId


T = TypeVar("T", bound="JsonApiRelationshipsLinksRootFolder")


@_attrs_define
class JsonApiRelationshipsLinksRootFolder:
    """Information about the root folder of a project.

    Attributes:
        data (JsonApiTypeId | Unset): An object containing the ``id`` and ``type`` properties of a resource.
        meta (JsonApiMetaLink | Unset): Meta-information on links to this resource.
    """

    data: JsonApiTypeId | Unset = UNSET
    meta: JsonApiMetaLink | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] | Unset = UNSET
        if not isinstance(self.data, Unset):
            data = self.data.to_dict()

        meta: dict[str, Any] | Unset = UNSET
        if not isinstance(self.meta, Unset):
            meta = self.meta.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if data is not UNSET:
            field_dict["data"] = data
        if meta is not UNSET:
            field_dict["meta"] = meta

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_meta_link import JsonApiMetaLink
        from ..models.json_api_type_id import JsonApiTypeId

        d = dict(src_dict)
        _data = d.pop("data", UNSET)
        data: JsonApiTypeId | Unset
        if isinstance(_data, Unset):
            data = UNSET
        else:
            data = JsonApiTypeId.from_dict(_data)

        _meta = d.pop("meta", UNSET)
        meta: JsonApiMetaLink | Unset
        if isinstance(_meta, Unset):
            meta = UNSET
        else:
            meta = JsonApiMetaLink.from_dict(_meta)

        json_api_relationships_links_root_folder = cls(
            data=data,
            meta=meta,
        )

        json_api_relationships_links_root_folder.additional_properties = d
        return json_api_relationships_links_root_folder

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
