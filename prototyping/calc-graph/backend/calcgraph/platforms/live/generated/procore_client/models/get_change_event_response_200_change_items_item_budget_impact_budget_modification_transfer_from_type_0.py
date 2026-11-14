from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0",
)


@_attrs_define
class GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0:
    """Source Budget (Line Item) Code the amount was transferred from. Null when the modification has no source line item.

    Attributes:
        id (int | Unset): ID of the source Budget Line Item. Use as the budget line item identifier in Budget tool
            requests.
        name (str | Unset): Display name of the source Budget Code.
    """

    id: int | Unset = UNSET
    name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_from_type_0 = cls(
            id=id,
            name=name,
        )

        get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_from_type_0.additional_properties = d
        return get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_from_type_0

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
