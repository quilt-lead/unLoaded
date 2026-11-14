from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_attachments_item import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedAttachmentsItem,
    )
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_by import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedBy,
    )
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem,
    )
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_to_item import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedToItem,
    )


T = TypeVar("T", bound="ListSubmittalsResponse200ItemLastDistributedSubmittalType0")


@_attrs_define
class ListSubmittalsResponse200ItemLastDistributedSubmittalType0:
    """
    Attributes:
        distributed_attachments
            (list[ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedAttachmentsItem] | Unset):
        distributed_by (ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedBy | Unset):
        distributed_responses (list[ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem]
            | Unset):
        distributed_to (list[ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedToItem] | Unset):
        id (int | Unset):
        message (str | Unset):
        sent_at (datetime.datetime | Unset):
    """

    distributed_attachments: (
        list[
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedAttachmentsItem
        ]
        | Unset
    ) = UNSET
    distributed_by: (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedBy | Unset
    ) = UNSET
    distributed_responses: (
        list[
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem
        ]
        | Unset
    ) = UNSET
    distributed_to: (
        list[
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedToItem
        ]
        | Unset
    ) = UNSET
    id: int | Unset = UNSET
    message: str | Unset = UNSET
    sent_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        distributed_attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distributed_attachments, Unset):
            distributed_attachments = []
            for distributed_attachments_item_data in self.distributed_attachments:
                distributed_attachments_item = (
                    distributed_attachments_item_data.to_dict()
                )
                distributed_attachments.append(distributed_attachments_item)

        distributed_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.distributed_by, Unset):
            distributed_by = self.distributed_by.to_dict()

        distributed_responses: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distributed_responses, Unset):
            distributed_responses = []
            for distributed_responses_item_data in self.distributed_responses:
                distributed_responses_item = distributed_responses_item_data.to_dict()
                distributed_responses.append(distributed_responses_item)

        distributed_to: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distributed_to, Unset):
            distributed_to = []
            for distributed_to_item_data in self.distributed_to:
                distributed_to_item = distributed_to_item_data.to_dict()
                distributed_to.append(distributed_to_item)

        id = self.id

        message = self.message

        sent_at: str | Unset = UNSET
        if not isinstance(self.sent_at, Unset):
            sent_at = self.sent_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if distributed_attachments is not UNSET:
            field_dict["distributed_attachments"] = distributed_attachments
        if distributed_by is not UNSET:
            field_dict["distributed_by"] = distributed_by
        if distributed_responses is not UNSET:
            field_dict["distributed_responses"] = distributed_responses
        if distributed_to is not UNSET:
            field_dict["distributed_to"] = distributed_to
        if id is not UNSET:
            field_dict["id"] = id
        if message is not UNSET:
            field_dict["message"] = message
        if sent_at is not UNSET:
            field_dict["sent_at"] = sent_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_attachments_item import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedAttachmentsItem,
        )
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_by import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedBy,
        )
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem,
        )
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_to_item import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedToItem,
        )

        d = dict(src_dict)
        _distributed_attachments = d.pop("distributed_attachments", UNSET)
        distributed_attachments: (
            list[
                ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedAttachmentsItem
            ]
            | Unset
        ) = UNSET
        if _distributed_attachments is not UNSET:
            distributed_attachments = []
            for distributed_attachments_item_data in _distributed_attachments:
                distributed_attachments_item = ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedAttachmentsItem.from_dict(
                    distributed_attachments_item_data
                )

                distributed_attachments.append(distributed_attachments_item)

        _distributed_by = d.pop("distributed_by", UNSET)
        distributed_by: (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedBy
            | Unset
        )
        if isinstance(_distributed_by, Unset):
            distributed_by = UNSET
        else:
            distributed_by = ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedBy.from_dict(
                _distributed_by
            )

        _distributed_responses = d.pop("distributed_responses", UNSET)
        distributed_responses: (
            list[
                ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem
            ]
            | Unset
        ) = UNSET
        if _distributed_responses is not UNSET:
            distributed_responses = []
            for distributed_responses_item_data in _distributed_responses:
                distributed_responses_item = ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem.from_dict(
                    distributed_responses_item_data
                )

                distributed_responses.append(distributed_responses_item)

        _distributed_to = d.pop("distributed_to", UNSET)
        distributed_to: (
            list[
                ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedToItem
            ]
            | Unset
        ) = UNSET
        if _distributed_to is not UNSET:
            distributed_to = []
            for distributed_to_item_data in _distributed_to:
                distributed_to_item = ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedToItem.from_dict(
                    distributed_to_item_data
                )

                distributed_to.append(distributed_to_item)

        id = d.pop("id", UNSET)

        message = d.pop("message", UNSET)

        _sent_at = d.pop("sent_at", UNSET)
        sent_at: datetime.datetime | Unset
        if isinstance(_sent_at, Unset):
            sent_at = UNSET
        else:
            sent_at = datetime.datetime.fromisoformat(_sent_at)

        list_submittals_response_200_item_last_distributed_submittal_type_0 = cls(
            distributed_attachments=distributed_attachments,
            distributed_by=distributed_by,
            distributed_responses=distributed_responses,
            distributed_to=distributed_to,
            id=id,
            message=message,
            sent_at=sent_at,
        )

        list_submittals_response_200_item_last_distributed_submittal_type_0.additional_properties = d
        return list_submittals_response_200_item_last_distributed_submittal_type_0

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
