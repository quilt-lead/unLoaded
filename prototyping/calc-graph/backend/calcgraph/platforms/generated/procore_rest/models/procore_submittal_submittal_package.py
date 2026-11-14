from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_submittal_submittal_package_attachments_item import (
        ProcoreSubmittalSubmittalPackageAttachmentsItem,
    )
    from ..models.procore_submittal_submittal_package_created_by import (
        ProcoreSubmittalSubmittalPackageCreatedBy,
    )


T = TypeVar("T", bound="ProcoreSubmittalSubmittalPackage")


@_attrs_define
class ProcoreSubmittalSubmittalPackage:
    """
    Attributes:
        attachments (list[ProcoreSubmittalSubmittalPackageAttachmentsItem] | Unset):
        attachments_count (int | Unset):
        created_by (ProcoreSubmittalSubmittalPackageCreatedBy | Unset):
        description (str | Unset):
        id (int | Unset):
        number (str | Unset):
        submittal_ids (list[int] | Unset):
        title (str | Unset):
    """

    attachments: list[ProcoreSubmittalSubmittalPackageAttachmentsItem] | Unset = UNSET
    attachments_count: int | Unset = UNSET
    created_by: ProcoreSubmittalSubmittalPackageCreatedBy | Unset = UNSET
    description: str | Unset = UNSET
    id: int | Unset = UNSET
    number: str | Unset = UNSET
    submittal_ids: list[int] | Unset = UNSET
    title: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        attachments_count = self.attachments_count

        created_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.created_by, Unset):
            created_by = self.created_by.to_dict()

        description = self.description

        id = self.id

        number = self.number

        submittal_ids: list[int] | Unset = UNSET
        if not isinstance(self.submittal_ids, Unset):
            submittal_ids = self.submittal_ids

        title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if attachments_count is not UNSET:
            field_dict["attachments_count"] = attachments_count
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if description is not UNSET:
            field_dict["description"] = description
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number
        if submittal_ids is not UNSET:
            field_dict["submittal_ids"] = submittal_ids
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_submittal_submittal_package_attachments_item import (
            ProcoreSubmittalSubmittalPackageAttachmentsItem,
        )
        from ..models.procore_submittal_submittal_package_created_by import (
            ProcoreSubmittalSubmittalPackageCreatedBy,
        )

        d = dict(src_dict)
        _attachments = d.pop("attachments", UNSET)
        attachments: list[ProcoreSubmittalSubmittalPackageAttachmentsItem] | Unset = (
            UNSET
        )
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = (
                    ProcoreSubmittalSubmittalPackageAttachmentsItem.from_dict(
                        attachments_item_data
                    )
                )

                attachments.append(attachments_item)

        attachments_count = d.pop("attachments_count", UNSET)

        _created_by = d.pop("created_by", UNSET)
        created_by: ProcoreSubmittalSubmittalPackageCreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = ProcoreSubmittalSubmittalPackageCreatedBy.from_dict(
                _created_by
            )

        description = d.pop("description", UNSET)

        id = d.pop("id", UNSET)

        number = d.pop("number", UNSET)

        submittal_ids = cast(list[int], d.pop("submittal_ids", UNSET))

        title = d.pop("title", UNSET)

        procore_submittal_submittal_package = cls(
            attachments=attachments,
            attachments_count=attachments_count,
            created_by=created_by,
            description=description,
            id=id,
            number=number,
            submittal_ids=submittal_ids,
            title=title,
        )

        procore_submittal_submittal_package.additional_properties = d
        return procore_submittal_submittal_package

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
