from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item_distributed_attachments_item import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemDistributedAttachmentsItem,
    )
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item_submittal_response import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemSubmittalResponse,
    )


T = TypeVar(
    "T",
    bound="ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem",
)


@_attrs_define
class ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem:
    """
    Attributes:
        comment (str | Unset):
        distributed_attachments (list[ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItem
            DistributedAttachmentsItem] | Unset):
        id (int | Unset):
        submittal_approver_id (int | Unset):
        submittal_response
            (ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemSubmittalResponse | Unset):
        submittal_response_id (int | Unset):
        user_id (int | Unset):
    """

    comment: str | Unset = UNSET
    distributed_attachments: (
        list[
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemDistributedAttachmentsItem
        ]
        | Unset
    ) = UNSET
    id: int | Unset = UNSET
    submittal_approver_id: int | Unset = UNSET
    submittal_response: (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemSubmittalResponse
        | Unset
    ) = UNSET
    submittal_response_id: int | Unset = UNSET
    user_id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        comment = self.comment

        distributed_attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distributed_attachments, Unset):
            distributed_attachments = []
            for distributed_attachments_item_data in self.distributed_attachments:
                distributed_attachments_item = (
                    distributed_attachments_item_data.to_dict()
                )
                distributed_attachments.append(distributed_attachments_item)

        id = self.id

        submittal_approver_id = self.submittal_approver_id

        submittal_response: dict[str, Any] | Unset = UNSET
        if not isinstance(self.submittal_response, Unset):
            submittal_response = self.submittal_response.to_dict()

        submittal_response_id = self.submittal_response_id

        user_id = self.user_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if comment is not UNSET:
            field_dict["comment"] = comment
        if distributed_attachments is not UNSET:
            field_dict["distributed_attachments"] = distributed_attachments
        if id is not UNSET:
            field_dict["id"] = id
        if submittal_approver_id is not UNSET:
            field_dict["submittal_approver_id"] = submittal_approver_id
        if submittal_response is not UNSET:
            field_dict["submittal_response"] = submittal_response
        if submittal_response_id is not UNSET:
            field_dict["submittal_response_id"] = submittal_response_id
        if user_id is not UNSET:
            field_dict["user_id"] = user_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item_distributed_attachments_item import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemDistributedAttachmentsItem,
        )
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item_submittal_response import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemSubmittalResponse,
        )

        d = dict(src_dict)
        comment = d.pop("comment", UNSET)

        _distributed_attachments = d.pop("distributed_attachments", UNSET)
        distributed_attachments: (
            list[
                ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemDistributedAttachmentsItem
            ]
            | Unset
        ) = UNSET
        if _distributed_attachments is not UNSET:
            distributed_attachments = []
            for distributed_attachments_item_data in _distributed_attachments:
                distributed_attachments_item = ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemDistributedAttachmentsItem.from_dict(
                    distributed_attachments_item_data
                )

                distributed_attachments.append(distributed_attachments_item)

        id = d.pop("id", UNSET)

        submittal_approver_id = d.pop("submittal_approver_id", UNSET)

        _submittal_response = d.pop("submittal_response", UNSET)
        submittal_response: (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemSubmittalResponse
            | Unset
        )
        if isinstance(_submittal_response, Unset):
            submittal_response = UNSET
        else:
            submittal_response = ListSubmittalsResponse200ItemLastDistributedSubmittalType0DistributedResponsesItemSubmittalResponse.from_dict(
                _submittal_response
            )

        submittal_response_id = d.pop("submittal_response_id", UNSET)

        user_id = d.pop("user_id", UNSET)

        list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item = cls(
            comment=comment,
            distributed_attachments=distributed_attachments,
            id=id,
            submittal_approver_id=submittal_approver_id,
            submittal_response=submittal_response,
            submittal_response_id=submittal_response_id,
            user_id=user_id,
        )

        list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item.additional_properties = d
        return list_submittals_response_200_item_last_distributed_submittal_type_0_distributed_responses_item

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
