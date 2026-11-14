from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListDrawingAreasResponse200ItemDrawingSetsItem")


@_attrs_define
class ListDrawingAreasResponse200ItemDrawingSetsItem:
    """Drawing Set

    Attributes:
        created_at (datetime.datetime | Unset): Drawing Set created at
        date (datetime.date | Unset): Drawing Set date
        drawing_revisions_count (int | Unset): Amount of Drawing Revisions
        id (int | Unset): Drawing Set ID
        name (str | Unset): Drawing Set name
        position (int | Unset): Drawing Set position
        project_id (int | Unset): Drawing Set project ID
        updated_at (datetime.datetime | Unset): Drawing Set updated at
    """

    created_at: datetime.datetime | Unset = UNSET
    date: datetime.date | Unset = UNSET
    drawing_revisions_count: int | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    position: int | Unset = UNSET
    project_id: int | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        date: str | Unset = UNSET
        if not isinstance(self.date, Unset):
            date = self.date.isoformat()

        drawing_revisions_count = self.drawing_revisions_count

        id = self.id

        name = self.name

        position = self.position

        project_id = self.project_id

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if date is not UNSET:
            field_dict["date"] = date
        if drawing_revisions_count is not UNSET:
            field_dict["drawing_revisions_count"] = drawing_revisions_count
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if position is not UNSET:
            field_dict["position"] = position
        if project_id is not UNSET:
            field_dict["project_id"] = project_id
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _date = d.pop("date", UNSET)
        date: datetime.date | Unset
        if isinstance(_date, Unset):
            date = UNSET
        else:
            date = datetime.date.fromisoformat(_date)

        drawing_revisions_count = d.pop("drawing_revisions_count", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        position = d.pop("position", UNSET)

        project_id = d.pop("project_id", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_drawing_areas_response_200_item_drawing_sets_item = cls(
            created_at=created_at,
            date=date,
            drawing_revisions_count=drawing_revisions_count,
            id=id,
            name=name,
            position=position,
            project_id=project_id,
            updated_at=updated_at,
        )

        list_drawing_areas_response_200_item_drawing_sets_item.additional_properties = d
        return list_drawing_areas_response_200_item_drawing_sets_item

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
