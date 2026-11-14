from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListDrawingsResponse200ItemCurrentRevisionType0")


@_attrs_define
class ListDrawingsResponse200ItemCurrentRevisionType0:
    """Current drawing revision

    Attributes:
        floorplan (bool | Unset): Revision floorplan status
        has_drawing_sketches (bool | Unset): Revision has drawing sketches status
        id (int | Unset): Revision ID
        large_thumbnail_url (str | Unset): Large thumbnail url
        pdf_size (int | Unset): PDF file size
        pdf_url (str | Unset): PDF url address
        png_size (int | Unset): PNG file size
        png_url (str | Unset): PNG url address
        revision_number (str | Unset): Revision number
        thumbnail_url (str | Unset): Thumbnail url
        updated_at (datetime.datetime | Unset): Revision updated at
    """

    floorplan: bool | Unset = UNSET
    has_drawing_sketches: bool | Unset = UNSET
    id: int | Unset = UNSET
    large_thumbnail_url: str | Unset = UNSET
    pdf_size: int | Unset = UNSET
    pdf_url: str | Unset = UNSET
    png_size: int | Unset = UNSET
    png_url: str | Unset = UNSET
    revision_number: str | Unset = UNSET
    thumbnail_url: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        floorplan = self.floorplan

        has_drawing_sketches = self.has_drawing_sketches

        id = self.id

        large_thumbnail_url = self.large_thumbnail_url

        pdf_size = self.pdf_size

        pdf_url = self.pdf_url

        png_size = self.png_size

        png_url = self.png_url

        revision_number = self.revision_number

        thumbnail_url = self.thumbnail_url

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if floorplan is not UNSET:
            field_dict["floorplan"] = floorplan
        if has_drawing_sketches is not UNSET:
            field_dict["has_drawing_sketches"] = has_drawing_sketches
        if id is not UNSET:
            field_dict["id"] = id
        if large_thumbnail_url is not UNSET:
            field_dict["large_thumbnail_url"] = large_thumbnail_url
        if pdf_size is not UNSET:
            field_dict["pdf_size"] = pdf_size
        if pdf_url is not UNSET:
            field_dict["pdf_url"] = pdf_url
        if png_size is not UNSET:
            field_dict["png_size"] = png_size
        if png_url is not UNSET:
            field_dict["png_url"] = png_url
        if revision_number is not UNSET:
            field_dict["revision_number"] = revision_number
        if thumbnail_url is not UNSET:
            field_dict["thumbnail_url"] = thumbnail_url
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        floorplan = d.pop("floorplan", UNSET)

        has_drawing_sketches = d.pop("has_drawing_sketches", UNSET)

        id = d.pop("id", UNSET)

        large_thumbnail_url = d.pop("large_thumbnail_url", UNSET)

        pdf_size = d.pop("pdf_size", UNSET)

        pdf_url = d.pop("pdf_url", UNSET)

        png_size = d.pop("png_size", UNSET)

        png_url = d.pop("png_url", UNSET)

        revision_number = d.pop("revision_number", UNSET)

        thumbnail_url = d.pop("thumbnail_url", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_drawings_response_200_item_current_revision_type_0 = cls(
            floorplan=floorplan,
            has_drawing_sketches=has_drawing_sketches,
            id=id,
            large_thumbnail_url=large_thumbnail_url,
            pdf_size=pdf_size,
            pdf_url=pdf_url,
            png_size=png_size,
            png_url=png_url,
            revision_number=revision_number,
            thumbnail_url=thumbnail_url,
            updated_at=updated_at,
        )

        list_drawings_response_200_item_current_revision_type_0.additional_properties = d
        return list_drawings_response_200_item_current_revision_type_0

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
