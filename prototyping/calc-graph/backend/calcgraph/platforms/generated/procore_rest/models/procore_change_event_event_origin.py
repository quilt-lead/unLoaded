from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreChangeEventEventOrigin")


@_attrs_define
class ProcoreChangeEventEventOrigin:
    """
    Attributes:
        display_name (str | Unset): name of event origin used for view
        origin_id (int | Unset): ID
        origin_type (str | Unset): type of object this change event originated from
        web_page_url (str | Unset): web page of event origin
    """

    display_name: str | Unset = UNSET
    origin_id: int | Unset = UNSET
    origin_type: str | Unset = UNSET
    web_page_url: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        display_name = self.display_name

        origin_id = self.origin_id

        origin_type = self.origin_type

        web_page_url = self.web_page_url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if display_name is not UNSET:
            field_dict["display_name"] = display_name
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id
        if origin_type is not UNSET:
            field_dict["origin_type"] = origin_type
        if web_page_url is not UNSET:
            field_dict["web_page_url"] = web_page_url

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        display_name = d.pop("display_name", UNSET)

        origin_id = d.pop("origin_id", UNSET)

        origin_type = d.pop("origin_type", UNSET)

        web_page_url = d.pop("web_page_url", UNSET)

        procore_change_event_event_origin = cls(
            display_name=display_name,
            origin_id=origin_id,
            origin_type=origin_type,
            web_page_url=web_page_url,
        )

        procore_change_event_event_origin.additional_properties = d
        return procore_change_event_event_origin

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
