from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_links_self_self import JsonApiLinksSelfSelf


T = TypeVar("T", bound="JsonApiLinksSelf")


@_attrs_define
class JsonApiLinksSelf:
    """An object containing the URI of the endpoint to access this resource.

    Attributes:
        self_ (JsonApiLinksSelfSelf | Unset): An object containing the URI of the endpoint to access this resource.
    """

    self_: JsonApiLinksSelfSelf | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        self_: dict[str, Any] | Unset = UNSET
        if not isinstance(self.self_, Unset):
            self_ = self.self_.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if self_ is not UNSET:
            field_dict["self"] = self_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_links_self_self import JsonApiLinksSelfSelf

        d = dict(src_dict)
        _self_ = d.pop("self", UNSET)
        self_: JsonApiLinksSelfSelf | Unset
        if isinstance(_self_, Unset):
            self_ = UNSET
        else:
            self_ = JsonApiLinksSelfSelf.from_dict(_self_)

        json_api_links_self = cls(
            self_=self_,
        )

        json_api_links_self.additional_properties = d
        return json_api_links_self

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
