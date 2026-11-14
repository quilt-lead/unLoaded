from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_submittal_response_201_approvers_item_attachments_item import (
        CreateSubmittalResponse201ApproversItemAttachmentsItem,
    )
    from ..models.create_submittal_response_201_approvers_item_response import (
        CreateSubmittalResponse201ApproversItemResponse,
    )
    from ..models.create_submittal_response_201_approvers_item_user import (
        CreateSubmittalResponse201ApproversItemUser,
    )


T = TypeVar("T", bound="CreateSubmittalResponse201ApproversItem")


@_attrs_define
class CreateSubmittalResponse201ApproversItem:
    """
    Attributes:
        approver_type (str | Unset): Role of Approver
        attachments (list[CreateSubmittalResponse201ApproversItemAttachmentsItem] | Unset): Attachments
        comment (None | str | Unset):
        days_to_respond (int | Unset):
        distributed (bool | Unset):
        due_date (datetime.date | None | Unset): Due Date
        email_sent_at (datetime.datetime | None | Unset): The datetime when the notification email was dispatched to the
            approver, expressed in the project's timezone. Null for historical records or when no email was sent. Note
            sent_date may be present while this field is null, when the approver was sent the submittal without an email
            notification.
        id (int | Unset): ID
        response (CreateSubmittalResponse201ApproversItemResponse | Unset):
        response_required (bool | Unset):
        returned_date (datetime.date | None | Unset): Returned Date
        sent_date (datetime.date | None | Unset): Sent Date
        submittal_associated_attachment_ids (list[int] | Unset): Submittal Associated Attachment IDs
        user (CreateSubmittalResponse201ApproversItemUser | Unset):
        workflow_group_number (int | Unset): The step in the workflow that the approver is on
    """

    approver_type: str | Unset = UNSET
    attachments: (
        list[CreateSubmittalResponse201ApproversItemAttachmentsItem] | Unset
    ) = UNSET
    comment: None | str | Unset = UNSET
    days_to_respond: int | Unset = UNSET
    distributed: bool | Unset = UNSET
    due_date: datetime.date | None | Unset = UNSET
    email_sent_at: datetime.datetime | None | Unset = UNSET
    id: int | Unset = UNSET
    response: CreateSubmittalResponse201ApproversItemResponse | Unset = UNSET
    response_required: bool | Unset = UNSET
    returned_date: datetime.date | None | Unset = UNSET
    sent_date: datetime.date | None | Unset = UNSET
    submittal_associated_attachment_ids: list[int] | Unset = UNSET
    user: CreateSubmittalResponse201ApproversItemUser | Unset = UNSET
    workflow_group_number: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        approver_type = self.approver_type

        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        comment: None | str | Unset
        if isinstance(self.comment, Unset):
            comment = UNSET
        else:
            comment = self.comment

        days_to_respond = self.days_to_respond

        distributed = self.distributed

        due_date: None | str | Unset
        if isinstance(self.due_date, Unset):
            due_date = UNSET
        elif isinstance(self.due_date, datetime.date):
            due_date = self.due_date.isoformat()
        else:
            due_date = self.due_date

        email_sent_at: None | str | Unset
        if isinstance(self.email_sent_at, Unset):
            email_sent_at = UNSET
        elif isinstance(self.email_sent_at, datetime.datetime):
            email_sent_at = self.email_sent_at.isoformat()
        else:
            email_sent_at = self.email_sent_at

        id = self.id

        response: dict[str, Any] | Unset = UNSET
        if not isinstance(self.response, Unset):
            response = self.response.to_dict()

        response_required = self.response_required

        returned_date: None | str | Unset
        if isinstance(self.returned_date, Unset):
            returned_date = UNSET
        elif isinstance(self.returned_date, datetime.date):
            returned_date = self.returned_date.isoformat()
        else:
            returned_date = self.returned_date

        sent_date: None | str | Unset
        if isinstance(self.sent_date, Unset):
            sent_date = UNSET
        elif isinstance(self.sent_date, datetime.date):
            sent_date = self.sent_date.isoformat()
        else:
            sent_date = self.sent_date

        submittal_associated_attachment_ids: list[int] | Unset = UNSET
        if not isinstance(self.submittal_associated_attachment_ids, Unset):
            submittal_associated_attachment_ids = (
                self.submittal_associated_attachment_ids
            )

        user: dict[str, Any] | Unset = UNSET
        if not isinstance(self.user, Unset):
            user = self.user.to_dict()

        workflow_group_number = self.workflow_group_number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if approver_type is not UNSET:
            field_dict["approver_type"] = approver_type
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if comment is not UNSET:
            field_dict["comment"] = comment
        if days_to_respond is not UNSET:
            field_dict["days_to_respond"] = days_to_respond
        if distributed is not UNSET:
            field_dict["distributed"] = distributed
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if email_sent_at is not UNSET:
            field_dict["email_sent_at"] = email_sent_at
        if id is not UNSET:
            field_dict["id"] = id
        if response is not UNSET:
            field_dict["response"] = response
        if response_required is not UNSET:
            field_dict["response_required"] = response_required
        if returned_date is not UNSET:
            field_dict["returned_date"] = returned_date
        if sent_date is not UNSET:
            field_dict["sent_date"] = sent_date
        if submittal_associated_attachment_ids is not UNSET:
            field_dict["submittal_associated_attachment_ids"] = (
                submittal_associated_attachment_ids
            )
        if user is not UNSET:
            field_dict["user"] = user
        if workflow_group_number is not UNSET:
            field_dict["workflow_group_number"] = workflow_group_number

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_submittal_response_201_approvers_item_attachments_item import (
            CreateSubmittalResponse201ApproversItemAttachmentsItem,
        )
        from ..models.create_submittal_response_201_approvers_item_response import (
            CreateSubmittalResponse201ApproversItemResponse,
        )
        from ..models.create_submittal_response_201_approvers_item_user import (
            CreateSubmittalResponse201ApproversItemUser,
        )

        d = dict(src_dict)
        approver_type = d.pop("approver_type", UNSET)

        _attachments = d.pop("attachments", UNSET)
        attachments: (
            list[CreateSubmittalResponse201ApproversItemAttachmentsItem] | Unset
        ) = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = (
                    CreateSubmittalResponse201ApproversItemAttachmentsItem.from_dict(
                        attachments_item_data
                    )
                )

                attachments.append(attachments_item)

        def _parse_comment(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        comment = _parse_comment(d.pop("comment", UNSET))

        days_to_respond = d.pop("days_to_respond", UNSET)

        distributed = d.pop("distributed", UNSET)

        def _parse_due_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                due_date_type_0 = datetime.date.fromisoformat(data)

                return due_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        due_date = _parse_due_date(d.pop("due_date", UNSET))

        def _parse_email_sent_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                email_sent_at_type_0 = datetime.datetime.fromisoformat(data)

                return email_sent_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        email_sent_at = _parse_email_sent_at(d.pop("email_sent_at", UNSET))

        id = d.pop("id", UNSET)

        _response = d.pop("response", UNSET)
        response: CreateSubmittalResponse201ApproversItemResponse | Unset
        if isinstance(_response, Unset):
            response = UNSET
        else:
            response = CreateSubmittalResponse201ApproversItemResponse.from_dict(
                _response
            )

        response_required = d.pop("response_required", UNSET)

        def _parse_returned_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                returned_date_type_0 = datetime.date.fromisoformat(data)

                return returned_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        returned_date = _parse_returned_date(d.pop("returned_date", UNSET))

        def _parse_sent_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                sent_date_type_0 = datetime.date.fromisoformat(data)

                return sent_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        sent_date = _parse_sent_date(d.pop("sent_date", UNSET))

        submittal_associated_attachment_ids = cast(
            list[int], d.pop("submittal_associated_attachment_ids", UNSET)
        )

        _user = d.pop("user", UNSET)
        user: CreateSubmittalResponse201ApproversItemUser | Unset
        if isinstance(_user, Unset):
            user = UNSET
        else:
            user = CreateSubmittalResponse201ApproversItemUser.from_dict(_user)

        workflow_group_number = d.pop("workflow_group_number", UNSET)

        create_submittal_response_201_approvers_item = cls(
            approver_type=approver_type,
            attachments=attachments,
            comment=comment,
            days_to_respond=days_to_respond,
            distributed=distributed,
            due_date=due_date,
            email_sent_at=email_sent_at,
            id=id,
            response=response,
            response_required=response_required,
            returned_date=returned_date,
            sent_date=sent_date,
            submittal_associated_attachment_ids=submittal_associated_attachment_ids,
            user=user,
            workflow_group_number=workflow_group_number,
        )

        create_submittal_response_201_approvers_item.additional_properties = d
        return create_submittal_response_201_approvers_item

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
