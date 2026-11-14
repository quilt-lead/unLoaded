from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_body_change_event_change_items_item_revenue_impact_estimate_calculation_strategy import (
    CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimateCalculationStrategy,
)
from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate"
)


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate:
    """
    Attributes:
        amount (None | str | Unset): estimated revenue amount
        calculation_strategy (CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimateCalculationStrategy |
            Unset): revenue calculation strategy
        quantity (None | str | Unset): estimated revenue quantity
        unit_cost (None | str | Unset): estimated unit cost
        unit_of_measure (None | str | Unset): unit of measure used
    """

    amount: None | str | Unset = UNSET
    calculation_strategy: (
        CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimateCalculationStrategy
        | Unset
    ) = UNSET
    quantity: None | str | Unset = UNSET
    unit_cost: None | str | Unset = UNSET
    unit_of_measure: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount: None | str | Unset
        if isinstance(self.amount, Unset):
            amount = UNSET
        else:
            amount = self.amount

        calculation_strategy: str | Unset = UNSET
        if not isinstance(self.calculation_strategy, Unset):
            calculation_strategy = self.calculation_strategy.value

        quantity: None | str | Unset
        if isinstance(self.quantity, Unset):
            quantity = UNSET
        else:
            quantity = self.quantity

        unit_cost: None | str | Unset
        if isinstance(self.unit_cost, Unset):
            unit_cost = UNSET
        else:
            unit_cost = self.unit_cost

        unit_of_measure: None | str | Unset
        if isinstance(self.unit_of_measure, Unset):
            unit_of_measure = UNSET
        else:
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

        def _parse_amount(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        amount = _parse_amount(d.pop("amount", UNSET))

        _calculation_strategy = d.pop("calculation_strategy", UNSET)
        calculation_strategy: (
            CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimateCalculationStrategy
            | Unset
        )
        if isinstance(_calculation_strategy, Unset):
            calculation_strategy = UNSET
        else:
            calculation_strategy = CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimateCalculationStrategy(
                _calculation_strategy
            )

        def _parse_quantity(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        quantity = _parse_quantity(d.pop("quantity", UNSET))

        def _parse_unit_cost(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_cost = _parse_unit_cost(d.pop("unit_cost", UNSET))

        def _parse_unit_of_measure(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_of_measure = _parse_unit_of_measure(d.pop("unit_of_measure", UNSET))

        create_change_event_body_change_event_change_items_item_revenue_impact_estimate = cls(
            amount=amount,
            calculation_strategy=calculation_strategy,
            quantity=quantity,
            unit_cost=unit_cost,
            unit_of_measure=unit_of_measure,
        )

        create_change_event_body_change_event_change_items_item_revenue_impact_estimate.additional_properties = d
        return create_change_event_body_change_event_change_items_item_revenue_impact_estimate

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
