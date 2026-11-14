from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_cost_impact_estimate_calculation_strategy import (
    CreateChangeEventResponse201ChangeItemsItemCostImpactEstimateCalculationStrategy,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate")


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate:
    """
    Attributes:
        amount (str | Unset): Estimated cost amount
        calculation_strategy (CreateChangeEventResponse201ChangeItemsItemCostImpactEstimateCalculationStrategy | Unset):
            Cost calculation strategy
        quantity (str | Unset): Estimated cost quantity
        unit_cost (str | Unset): Estimated unit cost
        unit_of_measure (str | Unset): Unit of measure used
    """

    amount: str | Unset = UNSET
    calculation_strategy: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactEstimateCalculationStrategy
        | Unset
    ) = UNSET
    quantity: str | Unset = UNSET
    unit_cost: str | Unset = UNSET
    unit_of_measure: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        calculation_strategy: str | Unset = UNSET
        if not isinstance(self.calculation_strategy, Unset):
            calculation_strategy = self.calculation_strategy.value

        quantity = self.quantity

        unit_cost = self.unit_cost

        unit_of_measure = self.unit_of_measure

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if calculation_strategy is not UNSET:
            field_dict["calculation_strategy"] = calculation_strategy
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if unit_cost is not UNSET:
            field_dict["unit_cost"] = unit_cost
        if unit_of_measure is not UNSET:
            field_dict["unit_of_measure"] = unit_of_measure

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        _calculation_strategy = d.pop("calculation_strategy", UNSET)
        calculation_strategy: (
            CreateChangeEventResponse201ChangeItemsItemCostImpactEstimateCalculationStrategy
            | Unset
        )
        if isinstance(_calculation_strategy, Unset):
            calculation_strategy = UNSET
        else:
            calculation_strategy = CreateChangeEventResponse201ChangeItemsItemCostImpactEstimateCalculationStrategy(
                _calculation_strategy
            )

        quantity = d.pop("quantity", UNSET)

        unit_cost = d.pop("unit_cost", UNSET)

        unit_of_measure = d.pop("unit_of_measure", UNSET)

        create_change_event_response_201_change_items_item_cost_impact_estimate = cls(
            amount=amount,
            calculation_strategy=calculation_strategy,
            quantity=quantity,
            unit_cost=unit_cost,
            unit_of_measure=unit_of_measure,
        )

        create_change_event_response_201_change_items_item_cost_impact_estimate.additional_properties = d
        return create_change_event_response_201_change_items_item_cost_impact_estimate

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
