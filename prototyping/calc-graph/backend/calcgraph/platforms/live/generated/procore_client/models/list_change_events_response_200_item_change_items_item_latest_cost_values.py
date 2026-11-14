from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_change_events_response_200_item_change_items_item_latest_cost_values_calculation_strategy import (
    ListChangeEventsResponse200ItemChangeItemsItemLatestCostValuesCalculationStrategy,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="ListChangeEventsResponse200ItemChangeItemsItemLatestCostValues")


@_attrs_define
class ListChangeEventsResponse200ItemChangeItemsItemLatestCostValues:
    """
    Attributes:
        amount (str | Unset): Latest cost amount
        amount_project_currency (str | Unset): Latest cost amount in project currency
        calculation_strategy (ListChangeEventsResponse200ItemChangeItemsItemLatestCostValuesCalculationStrategy |
            Unset): Latest cost calculation strategy
        quantity (str | Unset): Latest cost quantity
        unit_cost (str | Unset): Latest unit cost
        unit_cost_project_currency (str | Unset): Latest unit cost in project currency
        unit_of_measure (str | Unset): The unit of measure used
    """

    amount: str | Unset = UNSET
    amount_project_currency: str | Unset = UNSET
    calculation_strategy: (
        ListChangeEventsResponse200ItemChangeItemsItemLatestCostValuesCalculationStrategy
        | Unset
    ) = UNSET
    quantity: str | Unset = UNSET
    unit_cost: str | Unset = UNSET
    unit_cost_project_currency: str | Unset = UNSET
    unit_of_measure: str | Unset = UNSET
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

        unit_of_measure = self.unit_of_measure

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
        if unit_of_measure is not UNSET:
            field_dict["unit_of_measure"] = unit_of_measure

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        amount_project_currency = d.pop("amount_project_currency", UNSET)

        _calculation_strategy = d.pop("calculation_strategy", UNSET)
        calculation_strategy: (
            ListChangeEventsResponse200ItemChangeItemsItemLatestCostValuesCalculationStrategy
            | Unset
        )
        if isinstance(_calculation_strategy, Unset):
            calculation_strategy = UNSET
        else:
            calculation_strategy = ListChangeEventsResponse200ItemChangeItemsItemLatestCostValuesCalculationStrategy(
                _calculation_strategy
            )

        quantity = d.pop("quantity", UNSET)

        unit_cost = d.pop("unit_cost", UNSET)

        unit_cost_project_currency = d.pop("unit_cost_project_currency", UNSET)

        unit_of_measure = d.pop("unit_of_measure", UNSET)

        list_change_events_response_200_item_change_items_item_latest_cost_values = cls(
            amount=amount,
            amount_project_currency=amount_project_currency,
            calculation_strategy=calculation_strategy,
            quantity=quantity,
            unit_cost=unit_cost,
            unit_cost_project_currency=unit_cost_project_currency,
            unit_of_measure=unit_of_measure,
        )

        list_change_events_response_200_item_change_items_item_latest_cost_values.additional_properties = d
        return list_change_events_response_200_item_change_items_item_latest_cost_values

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
