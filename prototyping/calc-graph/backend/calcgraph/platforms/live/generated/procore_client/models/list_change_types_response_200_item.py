from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListChangeTypesResponse200Item")


@_attrs_define
class ListChangeTypesResponse200Item:
    """
    Attributes:
        abbreviation (None | str | Unset): Short code/abbreviation for the Change Type shown in compact UI contexts.
            Null when no abbreviation is set.
        change_type (str | Unset): Display name of the Change Type (e.g. Transfer, Allowance).
        company_id (int | Unset): ID of the Company that owns this Change Type. Pass as the company_id query parameter
            when listing Change Types.
        id (int | Unset): Unique identifier of the Change Type.
        show_in_select (bool | Unset): Whether this Change Type is available for selection in dropdowns/GUI.
    """

    abbreviation: None | str | Unset = UNSET
    change_type: str | Unset = UNSET
    company_id: int | Unset = UNSET
    id: int | Unset = UNSET
    show_in_select: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        abbreviation: None | str | Unset
        if isinstance(self.abbreviation, Unset):
            abbreviation = UNSET
        else:
            abbreviation = self.abbreviation

        change_type = self.change_type

        company_id = self.company_id

        id = self.id

        show_in_select = self.show_in_select

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if abbreviation is not UNSET:
            field_dict["abbreviation"] = abbreviation
        if change_type is not UNSET:
            field_dict["change_type"] = change_type
        if company_id is not UNSET:
            field_dict["company_id"] = company_id
        if id is not UNSET:
            field_dict["id"] = id
        if show_in_select is not UNSET:
            field_dict["show_in_select"] = show_in_select

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_abbreviation(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        abbreviation = _parse_abbreviation(d.pop("abbreviation", UNSET))

        change_type = d.pop("change_type", UNSET)

        company_id = d.pop("company_id", UNSET)

        id = d.pop("id", UNSET)

        show_in_select = d.pop("show_in_select", UNSET)

        list_change_types_response_200_item = cls(
            abbreviation=abbreviation,
            change_type=change_type,
            company_id=company_id,
            id=id,
            show_in_select=show_in_select,
        )

        list_change_types_response_200_item.additional_properties = d
        return list_change_types_response_200_item

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
