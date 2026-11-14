from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_rfi_response_200_questions_item_answers_item import (
        GetRfiResponse200QuestionsItemAnswersItem,
    )
    from ..models.get_rfi_response_200_questions_item_attachments_item import (
        GetRfiResponse200QuestionsItemAttachmentsItem,
    )


T = TypeVar("T", bound="GetRfiResponse200QuestionsItem")


@_attrs_define
class GetRfiResponse200QuestionsItem:
    """
    Attributes:
        answers (list[GetRfiResponse200QuestionsItemAnswersItem] | Unset): Answers
        attachments (list[GetRfiResponse200QuestionsItemAttachmentsItem] | Unset): Attachments
        created_by (str | Unset): Creator name
        id (int | Unset): ID
        plain_text_body (str | Unset): Plain text body
        question_date (datetime.datetime | Unset): Date
        rich_text_body (str | Unset): Rich text body
    """

    answers: list[GetRfiResponse200QuestionsItemAnswersItem] | Unset = UNSET
    attachments: list[GetRfiResponse200QuestionsItemAttachmentsItem] | Unset = UNSET
    created_by: str | Unset = UNSET
    id: int | Unset = UNSET
    plain_text_body: str | Unset = UNSET
    question_date: datetime.datetime | Unset = UNSET
    rich_text_body: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        answers: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.answers, Unset):
            answers = []
            for answers_item_data in self.answers:
                answers_item = answers_item_data.to_dict()
                answers.append(answers_item)

        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        created_by = self.created_by

        id = self.id

        plain_text_body = self.plain_text_body

        question_date: str | Unset = UNSET
        if not isinstance(self.question_date, Unset):
            question_date = self.question_date.isoformat()

        rich_text_body = self.rich_text_body

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if answers is not UNSET:
            field_dict["answers"] = answers
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if id is not UNSET:
            field_dict["id"] = id
        if plain_text_body is not UNSET:
            field_dict["plain_text_body"] = plain_text_body
        if question_date is not UNSET:
            field_dict["question_date"] = question_date
        if rich_text_body is not UNSET:
            field_dict["rich_text_body"] = rich_text_body

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.get_rfi_response_200_questions_item_answers_item import (
            GetRfiResponse200QuestionsItemAnswersItem,
        )
        from ..models.get_rfi_response_200_questions_item_attachments_item import (
            GetRfiResponse200QuestionsItemAttachmentsItem,
        )

        d = dict(src_dict)
        _answers = d.pop("answers", UNSET)
        answers: list[GetRfiResponse200QuestionsItemAnswersItem] | Unset = UNSET
        if _answers is not UNSET:
            answers = []
            for answers_item_data in _answers:
                answers_item = GetRfiResponse200QuestionsItemAnswersItem.from_dict(
                    answers_item_data
                )

                answers.append(answers_item)

        _attachments = d.pop("attachments", UNSET)
        attachments: list[GetRfiResponse200QuestionsItemAttachmentsItem] | Unset = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = (
                    GetRfiResponse200QuestionsItemAttachmentsItem.from_dict(
                        attachments_item_data
                    )
                )

                attachments.append(attachments_item)

        created_by = d.pop("created_by", UNSET)

        id = d.pop("id", UNSET)

        plain_text_body = d.pop("plain_text_body", UNSET)

        _question_date = d.pop("question_date", UNSET)
        question_date: datetime.datetime | Unset
        if isinstance(_question_date, Unset):
            question_date = UNSET
        else:
            question_date = datetime.datetime.fromisoformat(_question_date)

        rich_text_body = d.pop("rich_text_body", UNSET)

        get_rfi_response_200_questions_item = cls(
            answers=answers,
            attachments=attachments,
            created_by=created_by,
            id=id,
            plain_text_body=plain_text_body,
            question_date=question_date,
            rich_text_body=rich_text_body,
        )

        get_rfi_response_200_questions_item.additional_properties = d
        return get_rfi_response_200_questions_item

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
