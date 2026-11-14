from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="GetChangeEventResponse200ChangeItemsItemCostImpactNonCommitment"
)


@_attrs_define
class GetChangeEventResponse200ChangeItemsItemCostImpactNonCommitment:
    """
    Attributes:
        amount (str | Unset): Latest cost amount
    """

    amount: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        get_change_event_response_200_change_items_item_cost_impact_non_commitment = (
            cls(
                amount=amount,
            )
        )

        get_change_event_response_200_change_items_item_cost_impact_non_commitment.additional_properties = d
        return (
            get_change_event_response_200_change_items_item_cost_impact_non_commitment
        )

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
