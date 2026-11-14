from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="GetSubmittalResponse200AttachmentsItem")


@_attrs_define
class GetSubmittalResponse200AttachmentsItem:
    """
    Attributes:
        filename (str | Unset): Filename
        id (int | Unset): ID
        url (str | Unset): URL
    """

    filename: str | Unset = UNSET
    id: int | Unset = UNSET
    url: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        filename = self.filename

        id = self.id

        url = self.url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if filename is not UNSET:
            field_dict["filename"] = filename
        if id is not UNSET:
            field_dict["id"] = id
        if url is not UNSET:
            field_dict["url"] = url

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        filename = d.pop("filename", UNSET)

        id = d.pop("id", UNSET)

        url = d.pop("url", UNSET)

        get_submittal_response_200_attachments_item = cls(
            filename=filename,
            id=id,
            url=url,
        )

        get_submittal_response_200_attachments_item.additional_properties = d
        return get_submittal_response_200_attachments_item

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
