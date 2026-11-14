from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_submittals_response_200_item_submittal_package_type_0_attachments_item import (
        ListSubmittalsResponse200ItemSubmittalPackageType0AttachmentsItem,
    )
    from ..models.list_submittals_response_200_item_submittal_package_type_0_created_by import (
        ListSubmittalsResponse200ItemSubmittalPackageType0CreatedBy,
    )


T = TypeVar("T", bound="ListSubmittalsResponse200ItemSubmittalPackageType0")


@_attrs_define
class ListSubmittalsResponse200ItemSubmittalPackageType0:
    """
    Attributes:
        attachments (list[ListSubmittalsResponse200ItemSubmittalPackageType0AttachmentsItem] | Unset):
        created_by (ListSubmittalsResponse200ItemSubmittalPackageType0CreatedBy | Unset):
        description (str | Unset):
        id (int | Unset):
        number (str | Unset):
        specification_section_id (int | Unset):
        submittal_ids (list[int] | Unset):
        title (str | Unset):
        updated_at (datetime.datetime | Unset):
    """

    attachments: (
        list[ListSubmittalsResponse200ItemSubmittalPackageType0AttachmentsItem] | Unset
    ) = UNSET
    created_by: ListSubmittalsResponse200ItemSubmittalPackageType0CreatedBy | Unset = (
        UNSET
    )
    description: str | Unset = UNSET
    id: int | Unset = UNSET
    number: str | Unset = UNSET
    specification_section_id: int | Unset = UNSET
    submittal_ids: list[int] | Unset = UNSET
    title: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        created_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.created_by, Unset):
            created_by = self.created_by.to_dict()

        description = self.description

        id = self.id

        number = self.number

        specification_section_id = self.specification_section_id

        submittal_ids: list[int] | Unset = UNSET
        if not isinstance(self.submittal_ids, Unset):
            submittal_ids = self.submittal_ids

        title = self.title

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if description is not UNSET:
            field_dict["description"] = description
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number
        if specification_section_id is not UNSET:
            field_dict["specification_section_id"] = specification_section_id
        if submittal_ids is not UNSET:
            field_dict["submittal_ids"] = submittal_ids
        if title is not UNSET:
            field_dict["title"] = title
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_submittals_response_200_item_submittal_package_type_0_attachments_item import (
            ListSubmittalsResponse200ItemSubmittalPackageType0AttachmentsItem,
        )
        from ..models.list_submittals_response_200_item_submittal_package_type_0_created_by import (
            ListSubmittalsResponse200ItemSubmittalPackageType0CreatedBy,
        )

        d = dict(src_dict)
        _attachments = d.pop("attachments", UNSET)
        attachments: (
            list[ListSubmittalsResponse200ItemSubmittalPackageType0AttachmentsItem]
            | Unset
        ) = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = ListSubmittalsResponse200ItemSubmittalPackageType0AttachmentsItem.from_dict(
                    attachments_item_data
                )

                attachments.append(attachments_item)

        _created_by = d.pop("created_by", UNSET)
        created_by: ListSubmittalsResponse200ItemSubmittalPackageType0CreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = (
                ListSubmittalsResponse200ItemSubmittalPackageType0CreatedBy.from_dict(
                    _created_by
                )
            )

        description = d.pop("description", UNSET)

        id = d.pop("id", UNSET)

        number = d.pop("number", UNSET)

        specification_section_id = d.pop("specification_section_id", UNSET)

        submittal_ids = cast(list[int], d.pop("submittal_ids", UNSET))

        title = d.pop("title", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_submittals_response_200_item_submittal_package_type_0 = cls(
            attachments=attachments,
            created_by=created_by,
            description=description,
            id=id,
            number=number,
            specification_section_id=specification_section_id,
            submittal_ids=submittal_ids,
            title=title,
            updated_at=updated_at,
        )

        list_submittals_response_200_item_submittal_package_type_0.additional_properties = d
        return list_submittals_response_200_item_submittal_package_type_0

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
