from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_submittals_response_200_item_approvers_item_associated_attachments_item import (
        ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem,
    )
    from ..models.list_submittals_response_200_item_approvers_item_response import (
        ListSubmittalsResponse200ItemApproversItemResponse,
    )
    from ..models.list_submittals_response_200_item_approvers_item_user import (
        ListSubmittalsResponse200ItemApproversItemUser,
    )


T = TypeVar("T", bound="ListSubmittalsResponse200ItemApproversItem")


@_attrs_define
class ListSubmittalsResponse200ItemApproversItem:
    """
    Attributes:
        approver_type (str | Unset):
        associated_attachments (list[ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem] | Unset):
        comment (None | str | Unset):
        days_to_respond (int | Unset):
        due_date (datetime.date | Unset):
        email_sent_at (datetime.datetime | None | Unset): The datetime when the notification email was dispatched to the
            approver, expressed in the project's timezone. Null for historical records or when no email was sent. Note
            sent_date may be present while this field is null, when the approver was sent the submittal without an email
            notification.
        id (int | Unset):
        response (ListSubmittalsResponse200ItemApproversItemResponse | Unset):
        response_required (bool | Unset):
        returned_date (datetime.date | None | Unset):
        sent_date (datetime.date | None | Unset):
        user (ListSubmittalsResponse200ItemApproversItemUser | Unset):
        variance (float | None | Unset):
        workflow_group_number (int | Unset): The step in the workflow that the approver is on
    """

    approver_type: str | Unset = UNSET
    associated_attachments: (
        list[ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem]
        | Unset
    ) = UNSET
    comment: None | str | Unset = UNSET
    days_to_respond: int | Unset = UNSET
    due_date: datetime.date | Unset = UNSET
    email_sent_at: datetime.datetime | None | Unset = UNSET
    id: int | Unset = UNSET
    response: ListSubmittalsResponse200ItemApproversItemResponse | Unset = UNSET
    response_required: bool | Unset = UNSET
    returned_date: datetime.date | None | Unset = UNSET
    sent_date: datetime.date | None | Unset = UNSET
    user: ListSubmittalsResponse200ItemApproversItemUser | Unset = UNSET
    variance: float | None | Unset = UNSET
    workflow_group_number: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        approver_type = self.approver_type

        associated_attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.associated_attachments, Unset):
            associated_attachments = []
            for associated_attachments_item_data in self.associated_attachments:
                associated_attachments_item = associated_attachments_item_data.to_dict()
                associated_attachments.append(associated_attachments_item)

        comment: None | str | Unset
        if isinstance(self.comment, Unset):
            comment = UNSET
        else:
            comment = self.comment

        days_to_respond = self.days_to_respond

        due_date: str | Unset = UNSET
        if not isinstance(self.due_date, Unset):
            due_date = self.due_date.isoformat()

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

        user: dict[str, Any] | Unset = UNSET
        if not isinstance(self.user, Unset):
            user = self.user.to_dict()

        variance: float | None | Unset
        if isinstance(self.variance, Unset):
            variance = UNSET
        else:
            variance = self.variance

        workflow_group_number = self.workflow_group_number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if approver_type is not UNSET:
            field_dict["approver_type"] = approver_type
        if associated_attachments is not UNSET:
            field_dict["associated_attachments"] = associated_attachments
        if comment is not UNSET:
            field_dict["comment"] = comment
        if days_to_respond is not UNSET:
            field_dict["days_to_respond"] = days_to_respond
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
        if user is not UNSET:
            field_dict["user"] = user
        if variance is not UNSET:
            field_dict["variance"] = variance
        if workflow_group_number is not UNSET:
            field_dict["workflow_group_number"] = workflow_group_number

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_submittals_response_200_item_approvers_item_associated_attachments_item import (
            ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem,
        )
        from ..models.list_submittals_response_200_item_approvers_item_response import (
            ListSubmittalsResponse200ItemApproversItemResponse,
        )
        from ..models.list_submittals_response_200_item_approvers_item_user import (
            ListSubmittalsResponse200ItemApproversItemUser,
        )

        d = dict(src_dict)
        approver_type = d.pop("approver_type", UNSET)

        _associated_attachments = d.pop("associated_attachments", UNSET)
        associated_attachments: (
            list[ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem]
            | Unset
        ) = UNSET
        if _associated_attachments is not UNSET:
            associated_attachments = []
            for associated_attachments_item_data in _associated_attachments:
                associated_attachments_item = ListSubmittalsResponse200ItemApproversItemAssociatedAttachmentsItem.from_dict(
                    associated_attachments_item_data
                )

                associated_attachments.append(associated_attachments_item)

        def _parse_comment(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        comment = _parse_comment(d.pop("comment", UNSET))

        days_to_respond = d.pop("days_to_respond", UNSET)

        _due_date = d.pop("due_date", UNSET)
        due_date: datetime.date | Unset
        if isinstance(_due_date, Unset):
            due_date = UNSET
        else:
            due_date = datetime.date.fromisoformat(_due_date)

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
        response: ListSubmittalsResponse200ItemApproversItemResponse | Unset
        if isinstance(_response, Unset):
            response = UNSET
        else:
            response = ListSubmittalsResponse200ItemApproversItemResponse.from_dict(
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

        _user = d.pop("user", UNSET)
        user: ListSubmittalsResponse200ItemApproversItemUser | Unset
        if isinstance(_user, Unset):
            user = UNSET
        else:
            user = ListSubmittalsResponse200ItemApproversItemUser.from_dict(_user)

        def _parse_variance(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        variance = _parse_variance(d.pop("variance", UNSET))

        workflow_group_number = d.pop("workflow_group_number", UNSET)

        list_submittals_response_200_item_approvers_item = cls(
            approver_type=approver_type,
            associated_attachments=associated_attachments,
            comment=comment,
            days_to_respond=days_to_respond,
            due_date=due_date,
            email_sent_at=email_sent_at,
            id=id,
            response=response,
            response_required=response_required,
            returned_date=returned_date,
            sent_date=sent_date,
            user=user,
            variance=variance,
            workflow_group_number=workflow_group_number,
        )

        list_submittals_response_200_item_approvers_item.additional_properties = d
        return list_submittals_response_200_item_approvers_item

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
