from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_links_related_related import JsonApiLinksRelatedRelated


T = TypeVar("T", bound="JsonApiLinksRelated")


@_attrs_define
class JsonApiLinksRelated:
    """Contains the endpoint you can use to retrieve the related resources.

    Attributes:
        related (JsonApiLinksRelatedRelated | Unset): An object containing the endpoint to retrieve
            a list of related resources.
    """

    related: JsonApiLinksRelatedRelated | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        related: dict[str, Any] | Unset = UNSET
        if not isinstance(self.related, Unset):
            related = self.related.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if related is not UNSET:
            field_dict["related"] = related

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_links_related_related import JsonApiLinksRelatedRelated

        d = dict(src_dict)
        _related = d.pop("related", UNSET)
        related: JsonApiLinksRelatedRelated | Unset
        if isinstance(_related, Unset):
            related = UNSET
        else:
            related = JsonApiLinksRelatedRelated.from_dict(_related)

        json_api_links_related = cls(
            related=related,
        )

        json_api_links_related.additional_properties = d
        return json_api_links_related

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
