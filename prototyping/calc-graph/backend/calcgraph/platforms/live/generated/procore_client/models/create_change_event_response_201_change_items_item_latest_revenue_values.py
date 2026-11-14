from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_latest_revenue_values_calculation_strategy import (
    CreateChangeEventResponse201ChangeItemsItemLatestRevenueValuesCalculationStrategy,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventResponse201ChangeItemsItemLatestRevenueValues")


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemLatestRevenueValues:
    """
    Attributes:
        amount (str | Unset): Latest revenue amount
        amount_project_currency (str | Unset): Latest revenue amount in project currency
        calculation_strategy (CreateChangeEventResponse201ChangeItemsItemLatestRevenueValuesCalculationStrategy |
            Unset): Latest revenue calculation strategy
        quantity (str | Unset): Latest revenue quantity
        unit_cost (str | Unset): Latest revenue unit cost
        unit_cost_project_currency (str | Unset): Latest revenue unit cost in project currency
    """

    amount: str | Unset = UNSET
    amount_project_currency: str | Unset = UNSET
    calculation_strategy: (
        CreateChangeEventResponse201ChangeItemsItemLatestRevenueValuesCalculationStrategy
        | Unset
    ) = UNSET
    quantity: str | Unset = UNSET
    unit_cost: str | Unset = UNSET
    unit_cost_project_currency: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        amount_project_currency = self.amount_project_currency

        calculation_strategy: str | Unset = UNSET
        if not isinstance(self.calculation_strategy, Unset):
            calculation_strategy = self.calculation_strategy.value

        quantity = self.quantity

        unit_cost = self.unit_cost

        unit_cost_project_currency = self.unit_cost_project_currency

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if amount_project_currency is not UNSET:
            field_dict["amount_project_currency"] = amount_project_currency
        if calculation_strategy is not UNSET:
            field_dict["calculation_strategy"] = calculation_strategy
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if unit_cost is not UNSET:
            field_dict["unit_cost"] = unit_cost
        if unit_cost_project_currency is not UNSET:
            field_dict["unit_cost_project_currency"] = unit_cost_project_currency

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        amount_project_currency = d.pop("amount_project_currency", UNSET)

        _calculation_strategy = d.pop("calculation_strategy", UNSET)
        calculation_strategy: (
            CreateChangeEventResponse201ChangeItemsItemLatestRevenueValuesCalculationStrategy
            | Unset
        )
        if isinstance(_calculation_strategy, Unset):
            calculation_strategy = UNSET
        else:
            calculation_strategy = CreateChangeEventResponse201ChangeItemsItemLatestRevenueValuesCalculationStrategy(
                _calculation_strategy
            )

        quantity = d.pop("quantity", UNSET)

        unit_cost = d.pop("unit_cost", UNSET)

        unit_cost_project_currency = d.pop("unit_cost_project_currency", UNSET)

        create_change_event_response_201_change_items_item_latest_revenue_values = cls(
            amount=amount,
            amount_project_currency=amount_project_currency,
            calculation_strategy=calculation_strategy,
            quantity=quantity,
            unit_cost=unit_cost,
            unit_cost_project_currency=unit_cost_project_currency,
        )

        create_change_event_response_201_change_items_item_latest_revenue_values.additional_properties = d
        return create_change_event_response_201_change_items_item_latest_revenue_values

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
