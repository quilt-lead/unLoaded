from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issue_linked_documents_item_details import (
        IssueLinkedDocumentsItemDetails,
    )


T = TypeVar("T", bound="IssueLinkedDocumentsItem")


@_attrs_define
class IssueLinkedDocumentsItem:
    """
    Attributes:
        closed_at (str | Unset): The date and time the pushpin issue was closed, in ISO8601 format.
        closed_at_version (int | Unset): The version of the file when the pushpin issue was closed.
        closed_by (str | Unset): The Autodesk ID of the user who closed the pushpin issue.
        created_at (str | Unset): The date and time the pushpin was created, in ISO8601 format.
        created_at_version (int | Unset): The version of the file the pushin issue was added to. For information about
            file versions, see the Data Management API.
        created_by (str | Unset): The Autodesk ID of the user who created the pushpin issue.
        details (IssueLinkedDocumentsItemDetails | Unset): Information about the individual viewable.
        type_ (str | Unset): The type of file. Possible values:
            TwoDVectorPushpin (3D models) TwoDRasterPushpin (2D sheets and views)
        urn (str | Unset): The ID of the file associated with the issue (pushpin). Note the we do not currently support
            data associated with the ACC Build Sheet tool.
    """

    closed_at: str | Unset = UNSET
    closed_at_version: int | Unset = UNSET
    closed_by: str | Unset = UNSET
    created_at: str | Unset = UNSET
    created_at_version: int | Unset = UNSET
    created_by: str | Unset = UNSET
    details: IssueLinkedDocumentsItemDetails | Unset = UNSET
    type_: str | Unset = UNSET
    urn: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        closed_at = self.closed_at

        closed_at_version = self.closed_at_version

        closed_by = self.closed_by

        created_at = self.created_at

        created_at_version = self.created_at_version

        created_by = self.created_by

        details: dict[str, Any] | Unset = UNSET
        if not isinstance(self.details, Unset):
            details = self.details.to_dict()

        type_ = self.type_

        urn = self.urn

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if closed_at is not UNSET:
            field_dict["closedAt"] = closed_at
        if closed_at_version is not UNSET:
            field_dict["closedAtVersion"] = closed_at_version
        if closed_by is not UNSET:
            field_dict["closedBy"] = closed_by
        if created_at is not UNSET:
            field_dict["createdAt"] = created_at
        if created_at_version is not UNSET:
            field_dict["createdAtVersion"] = created_at_version
        if created_by is not UNSET:
            field_dict["createdBy"] = created_by
        if details is not UNSET:
            field_dict["details"] = details
        if type_ is not UNSET:
            field_dict["type"] = type_
        if urn is not UNSET:
            field_dict["urn"] = urn

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_linked_documents_item_details import (
            IssueLinkedDocumentsItemDetails,
        )

        d = dict(src_dict)
        closed_at = d.pop("closedAt", UNSET)

        closed_at_version = d.pop("closedAtVersion", UNSET)

        closed_by = d.pop("closedBy", UNSET)

        created_at = d.pop("createdAt", UNSET)

        created_at_version = d.pop("createdAtVersion", UNSET)

        created_by = d.pop("createdBy", UNSET)

        _details = d.pop("details", UNSET)
        details: IssueLinkedDocumentsItemDetails | Unset
        if isinstance(_details, Unset):
            details = UNSET
        else:
            details = IssueLinkedDocumentsItemDetails.from_dict(_details)

        type_ = d.pop("type", UNSET)

        urn = d.pop("urn", UNSET)

        issue_linked_documents_item = cls(
            closed_at=closed_at,
            closed_at_version=closed_at_version,
            closed_by=closed_by,
            created_at=created_at,
            created_at_version=created_at_version,
            created_by=created_by,
            details=details,
            type_=type_,
            urn=urn,
        )

        issue_linked_documents_item.additional_properties = d
        return issue_linked_documents_item

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
