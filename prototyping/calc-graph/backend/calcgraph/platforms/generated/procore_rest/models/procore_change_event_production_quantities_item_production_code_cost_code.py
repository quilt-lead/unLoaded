from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode"
)


@_attrs_define
class ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode:
    """cost code data

    Attributes:
        description (str | Unset): cost code sortable code and name
        id (int | Unset): cost code id
    """

    description: str | Unset = UNSET
    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if description is not UNSET:
            field_dict["description"] = description
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        description = d.pop("description", UNSET)

        id = d.pop("id", UNSET)

        procore_change_event_production_quantities_item_production_code_cost_code = cls(
            description=description,
            id=id,
        )

        procore_change_event_production_quantities_item_production_code_cost_code.additional_properties = d
        return procore_change_event_production_quantities_item_production_code_cost_code

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
