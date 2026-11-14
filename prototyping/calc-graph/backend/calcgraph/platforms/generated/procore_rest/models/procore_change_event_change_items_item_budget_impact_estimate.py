from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.procore_change_event_change_items_item_budget_impact_estimate_calculation_strategy import (
    ProcoreChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_change_items_item_budget_impact_estimate_transfer import (
        ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer,
    )


T = TypeVar("T", bound="ProcoreChangeEventChangeItemsItemBudgetImpactEstimate")


@_attrs_define
class ProcoreChangeEventChangeItemsItemBudgetImpactEstimate:
    """
    Attributes:
        amount (None | str | Unset): Estimated budget ROM amount
        amount_project_currency (None | str | Unset): Estimated budget ROM amount in project currency
        auto_balance (bool | None | Unset): Indicates whether the Budget ROM should be automatically balanced
        calculation_strategy (ProcoreChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy | Unset): Budget
            ROM calculation strategy
        quantity (None | str | Unset): Estimated budget ROM quantity
        transfer (ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer | Unset):
        unit_cost (None | str | Unset): Estimated budget ROM unit cost
        unit_cost_project_currency (None | str | Unset): Estimated budget ROM unit cost in project currency
    """

    amount: None | str | Unset = UNSET
    amount_project_currency: None | str | Unset = UNSET
    auto_balance: bool | None | Unset = UNSET
    calculation_strategy: (
        ProcoreChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy | Unset
    ) = UNSET
    quantity: None | str | Unset = UNSET
    transfer: ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer | Unset = (
        UNSET
    )
    unit_cost: None | str | Unset = UNSET
    unit_cost_project_currency: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount: None | str | Unset
        if isinstance(self.amount, Unset):
            amount = UNSET
        else:
            amount = self.amount

        amount_project_currency: None | str | Unset
        if isinstance(self.amount_project_currency, Unset):
            amount_project_currency = UNSET
        else:
            amount_project_currency = self.amount_project_currency

        auto_balance: bool | None | Unset
        if isinstance(self.auto_balance, Unset):
            auto_balance = UNSET
        else:
            auto_balance = self.auto_balance

        calculation_strategy: str | Unset = UNSET
        if not isinstance(self.calculation_strategy, Unset):
            calculation_strategy = self.calculation_strategy.value

        quantity: None | str | Unset
        if isinstance(self.quantity, Unset):
            quantity = UNSET
        else:
            quantity = self.quantity

        transfer: dict[str, Any] | Unset = UNSET
        if not isinstance(self.transfer, Unset):
            transfer = self.transfer.to_dict()

        unit_cost: None | str | Unset
        if isinstance(self.unit_cost, Unset):
            unit_cost = UNSET
        else:
            unit_cost = self.unit_cost

        unit_cost_project_currency: None | str | Unset
        if isinstance(self.unit_cost_project_currency, Unset):
            unit_cost_project_currency = UNSET
        else:
            unit_cost_project_currency = self.unit_cost_project_currency

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if amount_project_currency is not UNSET:
            field_dict["amount_project_currency"] = amount_project_currency
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
        if unit_cost_project_currency is not UNSET:
            field_dict["unit_cost_project_currency"] = unit_cost_project_currency

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_change_items_item_budget_impact_estimate_transfer import (
            ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer,
        )

        d = dict(src_dict)

        def _parse_amount(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        amount = _parse_amount(d.pop("amount", UNSET))

        def _parse_amount_project_currency(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        amount_project_currency = _parse_amount_project_currency(
            d.pop("amount_project_currency", UNSET)
        )

        def _parse_auto_balance(data: object) -> bool | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(bool | None | Unset, data)

        auto_balance = _parse_auto_balance(d.pop("auto_balance", UNSET))

        _calculation_strategy = d.pop("calculation_strategy", UNSET)
        calculation_strategy: (
            ProcoreChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy
            | Unset
        )
        if isinstance(_calculation_strategy, Unset):
            calculation_strategy = UNSET
        else:
            calculation_strategy = ProcoreChangeEventChangeItemsItemBudgetImpactEstimateCalculationStrategy(
                _calculation_strategy
            )

        def _parse_quantity(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        quantity = _parse_quantity(d.pop("quantity", UNSET))

        _transfer = d.pop("transfer", UNSET)
        transfer: ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer | Unset
        if isinstance(_transfer, Unset):
            transfer = UNSET
        else:
            transfer = (
                ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer.from_dict(
                    _transfer
                )
            )

        def _parse_unit_cost(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_cost = _parse_unit_cost(d.pop("unit_cost", UNSET))

        def _parse_unit_cost_project_currency(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        unit_cost_project_currency = _parse_unit_cost_project_currency(
            d.pop("unit_cost_project_currency", UNSET)
        )

        procore_change_event_change_items_item_budget_impact_estimate = cls(
            amount=amount,
            amount_project_currency=amount_project_currency,
            auto_balance=auto_balance,
            calculation_strategy=calculation_strategy,
            quantity=quantity,
            transfer=transfer,
            unit_cost=unit_cost,
            unit_cost_project_currency=unit_cost_project_currency,
        )

        procore_change_event_change_items_item_budget_impact_estimate.additional_properties = d
        return procore_change_event_change_items_item_budget_impact_estimate

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
