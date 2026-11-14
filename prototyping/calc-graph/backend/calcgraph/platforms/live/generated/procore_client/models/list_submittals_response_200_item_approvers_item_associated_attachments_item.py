from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem"
)


@_attrs_define
class ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem:
    """
    Attributes:
        additional_page_count (int | Unset):
        attached_at (datetime.datetime | Unset):
        attachment_id (int | Unset):
        content_type (str | Unset):
        document_markup_layer_id (int | None | Unset):
        file_unavailable (bool | Unset): Whether the underlying file is currently unavailable (e.g. still processing or
            removed). When true, `url`, `filename`, and `content_type` may be null.
        filename (str | Unset):
        id (int | Unset):
        markup_updated_at (datetime.datetime | None | Unset):
        state (str | Unset):
        updated_at (datetime.datetime | Unset):
        url (str | Unset):
        version_timestamp (datetime.datetime | Unset):
    """

    additional_page_count: int | Unset = UNSET
    attached_at: datetime.datetime | Unset = UNSET
    attachment_id: int | Unset = UNSET
    content_type: str | Unset = UNSET
    document_markup_layer_id: int | None | Unset = UNSET
    file_unavailable: bool | Unset = UNSET
    filename: str | Unset = UNSET
    id: int | Unset = UNSET
    markup_updated_at: datetime.datetime | None | Unset = UNSET
    state: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    url: str | Unset = UNSET
    version_timestamp: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        additional_page_count = self.additional_page_count

        attached_at: str | Unset = UNSET
        if not isinstance(self.attached_at, Unset):
            attached_at = self.attached_at.isoformat()

        attachment_id = self.attachment_id

        content_type = self.content_type

        document_markup_layer_id: int | None | Unset
        if isinstance(self.document_markup_layer_id, Unset):
            document_markup_layer_id = UNSET
        else:
            document_markup_layer_id = self.document_markup_layer_id

        file_unavailable = self.file_unavailable

        filename = self.filename

        id = self.id

        markup_updated_at: None | str | Unset
        if isinstance(self.markup_updated_at, Unset):
            markup_updated_at = UNSET
        elif isinstance(self.markup_updated_at, datetime.datetime):
            markup_updated_at = self.markup_updated_at.isoformat()
        else:
            markup_updated_at = self.markup_updated_at

        state = self.state

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        url = self.url

        version_timestamp: str | Unset = UNSET
        if not isinstance(self.version_timestamp, Unset):
            version_timestamp = self.version_timestamp.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if additional_page_count is not UNSET:
            field_dict["additional_page_count"] = additional_page_count
        if attached_at is not UNSET:
            field_dict["attached_at"] = attached_at
        if attachment_id is not UNSET:
            field_dict["attachment_id"] = attachment_id
        if content_type is not UNSET:
            field_dict["content_type"] = content_type
        if document_markup_layer_id is not UNSET:
            field_dict["document_markup_layer_id"] = document_markup_layer_id
        if file_unavailable is not UNSET:
            field_dict["file_unavailable"] = file_unavailable
        if filename is not UNSET:
            field_dict["filename"] = filename
        if id is not UNSET:
            field_dict["id"] = id
        if markup_updated_at is not UNSET:
            field_dict["markup_updated_at"] = markup_updated_at
        if state is not UNSET:
            field_dict["state"] = state
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at
        if url is not UNSET:
            field_dict["url"] = url
        if version_timestamp is not UNSET:
            field_dict["version_timestamp"] = version_timestamp

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        additional_page_count = d.pop("additional_page_count", UNSET)

        _attached_at = d.pop("attached_at", UNSET)
        attached_at: datetime.datetime | Unset
        if isinstance(_attached_at, Unset):
            attached_at = UNSET
        else:
            attached_at = datetime.datetime.fromisoformat(_attached_at)

        attachment_id = d.pop("attachment_id", UNSET)

        content_type = d.pop("content_type", UNSET)

        def _parse_document_markup_layer_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        document_markup_layer_id = _parse_document_markup_layer_id(
            d.pop("document_markup_layer_id", UNSET)
        )

        file_unavailable = d.pop("file_unavailable", UNSET)

        filename = d.pop("filename", UNSET)

        id = d.pop("id", UNSET)

        def _parse_markup_updated_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                markup_updated_at_type_0 = datetime.datetime.fromisoformat(data)

                return markup_updated_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        markup_updated_at = _parse_markup_updated_at(d.pop("markup_updated_at", UNSET))

        state = d.pop("state", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        url = d.pop("url", UNSET)

        _version_timestamp = d.pop("version_timestamp", UNSET)
        version_timestamp: datetime.datetime | Unset
        if isinstance(_version_timestamp, Unset):
            version_timestamp = UNSET
        else:
            version_timestamp = datetime.datetime.fromisoformat(_version_timestamp)

        list_submittals_response_200_item_approvers_item_associated_attachments_item = (
            cls(
                additional_page_count=additional_page_count,
                attached_at=attached_at,
                attachment_id=attachment_id,
                content_type=content_type,
                document_markup_layer_id=document_markup_layer_id,
                file_unavailable=file_unavailable,
                filename=filename,
                id=id,
                markup_updated_at=markup_updated_at,
                state=state,
                updated_at=updated_at,
                url=url,
                version_timestamp=version_timestamp,
            )
        )

        list_submittals_response_200_item_approvers_item_associated_attachments_item.additional_properties = d
        return (
            list_submittals_response_200_item_approvers_item_associated_attachments_item
        )

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
