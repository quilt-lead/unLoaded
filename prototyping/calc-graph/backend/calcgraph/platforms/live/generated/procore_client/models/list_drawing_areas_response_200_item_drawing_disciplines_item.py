from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListDrawingAreasResponse200ItemDrawingDisciplinesItem")


@_attrs_define
class ListDrawingAreasResponse200ItemDrawingDisciplinesItem:
    """
    Attributes:
        id (int | Unset): Drawing Discipline ID
        name (str | Unset): Drawing Discipline name
        position (int | Unset): Drawing Discipline position
    """

    id: int | Unset = UNSET
    name: str | Unset = UNSET
    position: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        position = self.position

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if position is not UNSET:
            field_dict["position"] = position

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        position = d.pop("position", UNSET)

        list_drawing_areas_response_200_item_drawing_disciplines_item = cls(
            id=id,
            name=name,
            position=position,
        )

        list_drawing_areas_response_200_item_drawing_disciplines_item.additional_properties = d
        return list_drawing_areas_response_200_item_drawing_disciplines_item

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
