from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="IssueLinkedDocumentsItemDetailsViewable")


@_attrs_define
class IssueLinkedDocumentsItemDetailsViewable:
    """The individual viewable associated with the issue (pushpin). This is relevant for both individual 2D sheets and
    views within a 3D model, and individual PDF sheets within a multi-sheet PDF file. It is only relevant if the issue
    is associated with a file.

        Attributes:
            guid (str | Unset): The ID of the viewable (guid).
            id (str | Unset): Not relevant
            is_3d (bool | Unset): True if it is a 3D viewable false if it is a 2D viewable
            name (str | Unset): The name of the viewable.
                Max length: 1000
            viewable_id (str | Unset): Not relevant
    """

    guid: str | Unset = UNSET
    id: str | Unset = UNSET
    is_3d: bool | Unset = UNSET
    name: str | Unset = UNSET
    viewable_id: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        guid = self.guid

        id = self.id

        is_3d = self.is_3d

        name = self.name

        viewable_id = self.viewable_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if guid is not UNSET:
            field_dict["guid"] = guid
        if id is not UNSET:
            field_dict["id"] = id
        if is_3d is not UNSET:
            field_dict["is3D"] = is_3d
        if name is not UNSET:
            field_dict["name"] = name
        if viewable_id is not UNSET:
            field_dict["viewableId"] = viewable_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        guid = d.pop("guid", UNSET)

        id = d.pop("id", UNSET)

        is_3d = d.pop("is3D", UNSET)

        name = d.pop("name", UNSET)

        viewable_id = d.pop("viewableId", UNSET)

        issue_linked_documents_item_details_viewable = cls(
            guid=guid,
            id=id,
            is_3d=is_3d,
            name=name,
            viewable_id=viewable_id,
        )

        issue_linked_documents_item_details_viewable.additional_properties = d
        return issue_linked_documents_item_details_viewable

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
