from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreBudgetLineItemWbsCode")


@_attrs_define
class ProcoreBudgetLineItemWbsCode:
    """Work Breakdown Structure (WBS) code this line item is budgeted against.

    Attributes:
        description (str | Unset): Human-readable description of the WBS code.
        flat_code (str | Unset): Flattened WBS code string combining all segment values.
        id (int | Unset): Unique identifier of the WBS code. Pass as wbs_code_id when creating or updating a line item.
    """

    description: str | Unset = UNSET
    flat_code: str | Unset = UNSET
    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        flat_code = self.flat_code

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if description is not UNSET:
            field_dict["description"] = description
        if flat_code is not UNSET:
            field_dict["flat_code"] = flat_code
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        description = d.pop("description", UNSET)

        flat_code = d.pop("flat_code", UNSET)

        id = d.pop("id", UNSET)

        procore_budget_line_item_wbs_code = cls(
            description=description,
            flat_code=flat_code,
            id=id,
        )

        procore_budget_line_item_wbs_code.additional_properties = d
        return procore_budget_line_item_wbs_code

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
