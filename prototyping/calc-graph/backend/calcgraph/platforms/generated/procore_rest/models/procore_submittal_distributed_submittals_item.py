from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_submittal_distributed_submittals_item_distributed_by import (
        ProcoreSubmittalDistributedSubmittalsItemDistributedBy,
    )
    from ..models.procore_submittal_distributed_submittals_item_distributed_to_item import (
        ProcoreSubmittalDistributedSubmittalsItemDistributedToItem,
    )
    from ..models.procore_submittal_distributed_submittals_item_final_attachments_item import (
        ProcoreSubmittalDistributedSubmittalsItemFinalAttachmentsItem,
    )


T = TypeVar("T", bound="ProcoreSubmittalDistributedSubmittalsItem")


@_attrs_define
class ProcoreSubmittalDistributedSubmittalsItem:
    """
    Attributes:
        distributed_by (ProcoreSubmittalDistributedSubmittalsItemDistributedBy | Unset):
        distributed_to (list[ProcoreSubmittalDistributedSubmittalsItemDistributedToItem] | Unset):
        final_attachments (list[ProcoreSubmittalDistributedSubmittalsItemFinalAttachmentsItem] | Unset):
        id (int | Unset):
        message (str | Unset):
        selected_approver_ids (list[int] | Unset): List of Submittal Approver IDs for approvers selected to be
            distributed
        sent_at (datetime.datetime | Unset):
    """

    distributed_by: ProcoreSubmittalDistributedSubmittalsItemDistributedBy | Unset = (
        UNSET
    )
    distributed_to: (
        list[ProcoreSubmittalDistributedSubmittalsItemDistributedToItem] | Unset
    ) = UNSET
    final_attachments: (
        list[ProcoreSubmittalDistributedSubmittalsItemFinalAttachmentsItem] | Unset
    ) = UNSET
    id: int | Unset = UNSET
    message: str | Unset = UNSET
    selected_approver_ids: list[int] | Unset = UNSET
    sent_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        distributed_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.distributed_by, Unset):
            distributed_by = self.distributed_by.to_dict()

        distributed_to: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distributed_to, Unset):
            distributed_to = []
            for distributed_to_item_data in self.distributed_to:
                distributed_to_item = distributed_to_item_data.to_dict()
                distributed_to.append(distributed_to_item)

        final_attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.final_attachments, Unset):
            final_attachments = []
            for final_attachments_item_data in self.final_attachments:
                final_attachments_item = final_attachments_item_data.to_dict()
                final_attachments.append(final_attachments_item)

        id = self.id

        message = self.message

        selected_approver_ids: list[int] | Unset = UNSET
        if not isinstance(self.selected_approver_ids, Unset):
            selected_approver_ids = self.selected_approver_ids

        sent_at: str | Unset = UNSET
        if not isinstance(self.sent_at, Unset):
            sent_at = self.sent_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if distributed_by is not UNSET:
            field_dict["distributed_by"] = distributed_by
        if distributed_to is not UNSET:
            field_dict["distributed_to"] = distributed_to
        if final_attachments is not UNSET:
            field_dict["final_attachments"] = final_attachments
        if id is not UNSET:
            field_dict["id"] = id
        if message is not UNSET:
            field_dict["message"] = message
        if selected_approver_ids is not UNSET:
            field_dict["selected_approver_ids"] = selected_approver_ids
        if sent_at is not UNSET:
            field_dict["sent_at"] = sent_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_submittal_distributed_submittals_item_distributed_by import (
            ProcoreSubmittalDistributedSubmittalsItemDistributedBy,
        )
        from ..models.procore_submittal_distributed_submittals_item_distributed_to_item import (
            ProcoreSubmittalDistributedSubmittalsItemDistributedToItem,
        )
        from ..models.procore_submittal_distributed_submittals_item_final_attachments_item import (
            ProcoreSubmittalDistributedSubmittalsItemFinalAttachmentsItem,
        )

        d = dict(src_dict)
        _distributed_by = d.pop("distributed_by", UNSET)
        distributed_by: ProcoreSubmittalDistributedSubmittalsItemDistributedBy | Unset
        if isinstance(_distributed_by, Unset):
            distributed_by = UNSET
        else:
            distributed_by = (
                ProcoreSubmittalDistributedSubmittalsItemDistributedBy.from_dict(
                    _distributed_by
                )
            )

        _distributed_to = d.pop("distributed_to", UNSET)
        distributed_to: (
            list[ProcoreSubmittalDistributedSubmittalsItemDistributedToItem] | Unset
        ) = UNSET
        if _distributed_to is not UNSET:
            distributed_to = []
            for distributed_to_item_data in _distributed_to:
                distributed_to_item = ProcoreSubmittalDistributedSubmittalsItemDistributedToItem.from_dict(
                    distributed_to_item_data
                )

                distributed_to.append(distributed_to_item)

        _final_attachments = d.pop("final_attachments", UNSET)
        final_attachments: (
            list[ProcoreSubmittalDistributedSubmittalsItemFinalAttachmentsItem] | Unset
        ) = UNSET
        if _final_attachments is not UNSET:
            final_attachments = []
            for final_attachments_item_data in _final_attachments:
                final_attachments_item = ProcoreSubmittalDistributedSubmittalsItemFinalAttachmentsItem.from_dict(
                    final_attachments_item_data
                )

                final_attachments.append(final_attachments_item)

        id = d.pop("id", UNSET)

        message = d.pop("message", UNSET)

        selected_approver_ids = cast(list[int], d.pop("selected_approver_ids", UNSET))

        _sent_at = d.pop("sent_at", UNSET)
        sent_at: datetime.datetime | Unset
        if isinstance(_sent_at, Unset):
            sent_at = UNSET
        else:
            sent_at = datetime.datetime.fromisoformat(_sent_at)

        procore_submittal_distributed_submittals_item = cls(
            distributed_by=distributed_by,
            distributed_to=distributed_to,
            final_attachments=final_attachments,
            id=id,
            message=message,
            selected_approver_ids=selected_approver_ids,
            sent_at=sent_at,
        )

        procore_submittal_distributed_submittals_item.additional_properties = d
        return procore_submittal_distributed_submittals_item

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
