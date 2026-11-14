from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_drawing_areas_response_200_item_drawing_disciplines_item import (
        ListDrawingAreasResponse200ItemDrawingDisciplinesItem,
    )
    from ..models.list_drawing_areas_response_200_item_drawing_sets_item import (
        ListDrawingAreasResponse200ItemDrawingSetsItem,
    )


T = TypeVar("T", bound="ListDrawingAreasResponse200Item")


@_attrs_define
class ListDrawingAreasResponse200Item:
    """Drawing Area

    Attributes:
        created_at (datetime.datetime | Unset): Drawing Area created at timestamp
        deletable (bool | Unset): Whether the Drawing Area can be deleted
        description (str | Unset): Drawing Area Description
        drawing_disciplines (list[ListDrawingAreasResponse200ItemDrawingDisciplinesItem] | Unset): Array of Drawing
            Disciplines belonging to this Drawing Area. Included in the extended view.
        drawing_sets (list[ListDrawingAreasResponse200ItemDrawingSetsItem] | Unset): Array of Drawing Sets belonging to
            this Drawing Area. Included in the extended view.
        drawings_count (int | Unset): Amount of Drawings
        id (int | Unset): Drawing Area ID
        latest_revision_update (datetime.datetime | Unset): Timestamp of the most recent revision update in this Drawing
            Area, falls back to the area's updated_at if no revisions exist. Only included in the mfe view.
        name (str | Unset): Drawing Area name
        updated_at (datetime.datetime | Unset): Drawing Area updated at timestamp
    """

    created_at: datetime.datetime | Unset = UNSET
    deletable: bool | Unset = UNSET
    description: str | Unset = UNSET
    drawing_disciplines: (
        list[ListDrawingAreasResponse200ItemDrawingDisciplinesItem] | Unset
    ) = UNSET
    drawing_sets: list[ListDrawingAreasResponse200ItemDrawingSetsItem] | Unset = UNSET
    drawings_count: int | Unset = UNSET
    id: int | Unset = UNSET
    latest_revision_update: datetime.datetime | Unset = UNSET
    name: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        deletable = self.deletable

        description = self.description

        drawing_disciplines: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.drawing_disciplines, Unset):
            drawing_disciplines = []
            for drawing_disciplines_item_data in self.drawing_disciplines:
                drawing_disciplines_item = drawing_disciplines_item_data.to_dict()
                drawing_disciplines.append(drawing_disciplines_item)

        drawing_sets: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.drawing_sets, Unset):
            drawing_sets = []
            for drawing_sets_item_data in self.drawing_sets:
                drawing_sets_item = drawing_sets_item_data.to_dict()
                drawing_sets.append(drawing_sets_item)

        drawings_count = self.drawings_count

        id = self.id

        latest_revision_update: str | Unset = UNSET
        if not isinstance(self.latest_revision_update, Unset):
            latest_revision_update = self.latest_revision_update.isoformat()

        name = self.name

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if deletable is not UNSET:
            field_dict["deletable"] = deletable
        if description is not UNSET:
            field_dict["description"] = description
        if drawing_disciplines is not UNSET:
            field_dict["drawing_disciplines"] = drawing_disciplines
        if drawing_sets is not UNSET:
            field_dict["drawing_sets"] = drawing_sets
        if drawings_count is not UNSET:
            field_dict["drawings_count"] = drawings_count
        if id is not UNSET:
            field_dict["id"] = id
        if latest_revision_update is not UNSET:
            field_dict["latest_revision_update"] = latest_revision_update
        if name is not UNSET:
            field_dict["name"] = name
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_drawing_areas_response_200_item_drawing_disciplines_item import (
            ListDrawingAreasResponse200ItemDrawingDisciplinesItem,
        )
        from ..models.list_drawing_areas_response_200_item_drawing_sets_item import (
            ListDrawingAreasResponse200ItemDrawingSetsItem,
        )

        d = dict(src_dict)
        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        deletable = d.pop("deletable", UNSET)

        description = d.pop("description", UNSET)

        _drawing_disciplines = d.pop("drawing_disciplines", UNSET)
        drawing_disciplines: (
            list[ListDrawingAreasResponse200ItemDrawingDisciplinesItem] | Unset
        ) = UNSET
        if _drawing_disciplines is not UNSET:
            drawing_disciplines = []
            for drawing_disciplines_item_data in _drawing_disciplines:
                drawing_disciplines_item = (
                    ListDrawingAreasResponse200ItemDrawingDisciplinesItem.from_dict(
                        drawing_disciplines_item_data
                    )
                )

                drawing_disciplines.append(drawing_disciplines_item)

        _drawing_sets = d.pop("drawing_sets", UNSET)
        drawing_sets: list[ListDrawingAreasResponse200ItemDrawingSetsItem] | Unset = (
            UNSET
        )
        if _drawing_sets is not UNSET:
            drawing_sets = []
            for drawing_sets_item_data in _drawing_sets:
                drawing_sets_item = (
                    ListDrawingAreasResponse200ItemDrawingSetsItem.from_dict(
                        drawing_sets_item_data
                    )
                )

                drawing_sets.append(drawing_sets_item)

        drawings_count = d.pop("drawings_count", UNSET)

        id = d.pop("id", UNSET)

        _latest_revision_update = d.pop("latest_revision_update", UNSET)
        latest_revision_update: datetime.datetime | Unset
        if isinstance(_latest_revision_update, Unset):
            latest_revision_update = UNSET
        else:
            latest_revision_update = datetime.datetime.fromisoformat(
                _latest_revision_update
            )

        name = d.pop("name", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_drawing_areas_response_200_item = cls(
            created_at=created_at,
            deletable=deletable,
            description=description,
            drawing_disciplines=drawing_disciplines,
            drawing_sets=drawing_sets,
            drawings_count=drawings_count,
            id=id,
            latest_revision_update=latest_revision_update,
            name=name,
            updated_at=updated_at,
        )

        list_drawing_areas_response_200_item.additional_properties = d
        return list_drawing_areas_response_200_item

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
