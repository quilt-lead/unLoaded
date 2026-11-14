from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreSubmittalApproversItemAttachmentsItem")


@_attrs_define
class ProcoreSubmittalApproversItemAttachmentsItem:
    """
    Attributes:
        filename (str | Unset): Original filename of the attachment. Prefer `name`.
        id (int | Unset):
        name (str | Unset): Display name of the attachment file.
        url (str | Unset): Download URL of the attachment.
    """

    filename: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    url: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        filename = self.filename

        id = self.id

        name = self.name

        url = self.url

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if filename is not UNSET:
            field_dict["filename"] = filename
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if url is not UNSET:
            field_dict["url"] = url

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        filename = d.pop("filename", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        url = d.pop("url", UNSET)

        procore_submittal_approvers_item_attachments_item = cls(
            filename=filename,
            id=id,
            name=name,
            url=url,
        )

        procore_submittal_approvers_item_attachments_item.additional_properties = d
        return procore_submittal_approvers_item_attachments_item

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
