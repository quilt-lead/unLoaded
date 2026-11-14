from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_rfi_response_200_questions_item_answers_item_attachments_item import (
        GetRfiResponse200QuestionsItemAnswersItemAttachmentsItem,
    )


T = TypeVar("T", bound="GetRfiResponse200QuestionsItemAnswersItem")


@_attrs_define
class GetRfiResponse200QuestionsItemAnswersItem:
    """
    Attributes:
        answer_date (datetime.datetime | Unset): Date
        attachments (list[GetRfiResponse200QuestionsItemAnswersItemAttachmentsItem] | Unset): Attachments
        created_by (str | Unset): Creator name
        created_by_id (int | Unset): Creator ID
        id (int | Unset): ID
        official (bool | Unset): Official response, true if official
        plain_text_body (str | Unset): Plain text body
        rich_text_body (str | Unset): Rich text body
    """

    answer_date: datetime.datetime | Unset = UNSET
    attachments: (
        list[GetRfiResponse200QuestionsItemAnswersItemAttachmentsItem] | Unset
    ) = UNSET
    created_by: str | Unset = UNSET
    created_by_id: int | Unset = UNSET
    id: int | Unset = UNSET
    official: bool | Unset = UNSET
    plain_text_body: str | Unset = UNSET
    rich_text_body: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        answer_date: str | Unset = UNSET
        if not isinstance(self.answer_date, Unset):
            answer_date = self.answer_date.isoformat()

        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        created_by = self.created_by

        created_by_id = self.created_by_id

        id = self.id

        official = self.official

        plain_text_body = self.plain_text_body

        rich_text_body = self.rich_text_body

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if answer_date is not UNSET:
            field_dict["answer_date"] = answer_date
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if created_by_id is not UNSET:
            field_dict["created_by_id"] = created_by_id
        if id is not UNSET:
            field_dict["id"] = id
        if official is not UNSET:
            field_dict["official"] = official
        if plain_text_body is not UNSET:
            field_dict["plain_text_body"] = plain_text_body
        if rich_text_body is not UNSET:
            field_dict["rich_text_body"] = rich_text_body

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.get_rfi_response_200_questions_item_answers_item_attachments_item import (
            GetRfiResponse200QuestionsItemAnswersItemAttachmentsItem,
        )

        d = dict(src_dict)
        _answer_date = d.pop("answer_date", UNSET)
        answer_date: datetime.datetime | Unset
        if isinstance(_answer_date, Unset):
            answer_date = UNSET
        else:
            answer_date = datetime.datetime.fromisoformat(_answer_date)

        _attachments = d.pop("attachments", UNSET)
        attachments: (
            list[GetRfiResponse200QuestionsItemAnswersItemAttachmentsItem] | Unset
        ) = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = (
                    GetRfiResponse200QuestionsItemAnswersItemAttachmentsItem.from_dict(
                        attachments_item_data
                    )
                )

                attachments.append(attachments_item)

        created_by = d.pop("created_by", UNSET)

        created_by_id = d.pop("created_by_id", UNSET)

        id = d.pop("id", UNSET)

        official = d.pop("official", UNSET)

        plain_text_body = d.pop("plain_text_body", UNSET)

        rich_text_body = d.pop("rich_text_body", UNSET)

        get_rfi_response_200_questions_item_answers_item = cls(
            answer_date=answer_date,
            attachments=attachments,
            created_by=created_by,
            created_by_id=created_by_id,
            id=id,
            official=official,
            plain_text_body=plain_text_body,
            rich_text_body=rich_text_body,
        )

        get_rfi_response_200_questions_item_answers_item.additional_properties = d
        return get_rfi_response_200_questions_item_answers_item

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
