from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_body_change_event_change_items_item_budget_impact_estimate_calculation_strategy import (
    CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_body_change_event_change_items_item_budget_impact_estimate_transfer import (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer,
    )


T = TypeVar(
    "T", bound="CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimate"
)


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimate:
    """
    Attributes:
        amount (float | None | Unset): the estimated budget impact amount
        auto_balance (bool | None | Unset): indicates whether the Budget ROM should be automatically balanced
        calculation_strategy (CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy |
            Unset): the estimated budget impact calculation strategy
        quantity (float | None | Unset): the estimated budget impact quantity
        transfer (CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer | Unset):
        unit_cost (float | None | Unset): the estimated unit cost for budget impact
        unit_of_measure (None | str | Unset): the unit of measure used
    """

    amount: float | None | Unset = UNSET
    auto_balance: bool | None | Unset = UNSET
    calculation_strategy: (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy
        | Unset
    ) = UNSET
    quantity: float | None | Unset = UNSET
    transfer: (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer
        | Unset
    ) = UNSET
    unit_cost: float | None | Unset = UNSET
    unit_of_measure: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount: float | None | Unset
        if isinstance(self.amount, Unset):
            amount = UNSET
        else:
            amount = self.amount

        auto_balance: bool | None | Unset
        if isinstance(self.auto_balance, Unset):
            auto_balance = UNSET
        else:
            auto_balance = self.auto_balance

        calculation_strategy: str | Unset = UNSET
        if not isinstance(self.calculation_strategy, Unset):
            calculation_strategy = self.calculation_strategy.value

        quantity: float | None | Unset
        if isinstance(self.quantity, Unset):
            quantity = UNSET
        else:
            quantity = self.quantity

        transfer: dict[str, Any] | Unset = UNSET
        if not isinstance(self.transfer, Unset):
            transfer = self.transfer.to_dict()

        unit_cost: float | None | Unset
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
        if auto_balance is not UNSET:
            field_dict["auto_balance"] = auto_balance
        if calculation_strategy is not UNSET:
            field_dict["calculation_strategy"] = calculation_strategy
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if transfer is not UNSET:
            field_dict["transfer"] = transfer
        if unit_cost is not UNSET:
            field_dict["unit_cost"] = unit_cost
        if unit_of_measure is not UNSET:
            field_dict["unit_of_measure"] = unit_of_measure

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_body_change_event_change_items_item_budget_impact_estimate_transfer import (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer,
        )

        d = dict(src_dict)

        def _parse_amount(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        amount = _parse_amount(d.pop("amount", UNSET))

        def _parse_auto_balance(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        auto_balance = _parse_auto_balance(d.pop("auto_balance", UNSET))

        _calculation_strategy = d.pop("calculation_strategy", UNSET)
        calculation_strategy: (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy
            | Unset
        )
        if isinstance(_calculation_strategy, Unset):
            calculation_strategy = UNSET
        else:
            calculation_strategy = CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy(
                _calculation_strategy
            )

        def _parse_quantity(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        quantity = _parse_quantity(d.pop("quantity", UNSET))

        _transfer = d.pop("transfer", UNSET)
        transfer: (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer
            | Unset
        )
        if isinstance(_transfer, Unset):
            transfer = UNSET
        else:
            transfer = CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer.from_dict(
                _transfer
            )

        def _parse_unit_cost(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        unit_cost = _parse_unit_cost(d.pop("unit_cost", UNSET))

        def _parse_unit_of_measure(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_of_measure = _parse_unit_of_measure(d.pop("unit_of_measure", UNSET))

        create_change_event_body_change_event_change_items_item_budget_impact_estimate = cls(
            amount=amount,
            auto_balance=auto_balance,
            calculation_strategy=calculation_strategy,
            quantity=quantity,
            transfer=transfer,
            unit_cost=unit_cost,
            unit_of_measure=unit_of_measure,
        )

        create_change_event_body_change_event_change_items_item_budget_impact_estimate.additional_properties = d
        return create_change_event_body_change_event_change_items_item_budget_impact_estimate

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
