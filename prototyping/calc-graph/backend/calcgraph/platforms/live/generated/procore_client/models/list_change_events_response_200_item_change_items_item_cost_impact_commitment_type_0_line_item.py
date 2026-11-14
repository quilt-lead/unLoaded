from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem",
)


@_attrs_define
class ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem:
    """
    Attributes:
        amount (str | Unset): Total amount of the Line Item
        amount_project_currency (str | Unset): Total amount of the Line Item in project currency
        holder_id (int | None | Unset): ID of the entity that holds the Line Item (e.g. the Potential Change Order).
            Null for contract line items.
        id (int | Unset): ID of the Line Item
    """

    amount: str | Unset = UNSET
    amount_project_currency: str | Unset = UNSET
    holder_id: int | None | Unset = UNSET
    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        amount_project_currency = self.amount_project_currency

        holder_id: int | None | Unset
        if isinstance(self.holder_id, Unset):
            holder_id = UNSET
        else:
            holder_id = self.holder_id

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if amount_project_currency is not UNSET:
            field_dict["amount_project_currency"] = amount_project_currency
        if holder_id is not UNSET:
            field_dict["holder_id"] = holder_id
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        amount_project_currency = d.pop("amount_project_currency", UNSET)

        def _parse_holder_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        holder_id = _parse_holder_id(d.pop("holder_id", UNSET))

        id = d.pop("id", UNSET)

        list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_line_item = cls(
            amount=amount,
            amount_project_currency=amount_project_currency,
            holder_id=holder_id,
            id=id,
        )

        list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_line_item.additional_properties = d
        return list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_line_item

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
