from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_budget_line_item_currency_configuration import (
        ProcoreBudgetLineItemCurrencyConfiguration,
    )
    from ..models.procore_budget_line_item_wbs_code import ProcoreBudgetLineItemWbsCode


T = TypeVar("T", bound="ProcoreBudgetLineItem")


@_attrs_define
class ProcoreBudgetLineItem:
    """Budget Line Item

    Attributes:
        calculation_strategy (str | Unset): How original_budget_amount is derived, such as entered directly ('manual')
            or computed from quantity and unit_cost ('automatic').
        currency_configuration (ProcoreBudgetLineItemCurrencyConfiguration | Unset): Currency in which this line item's
            monetary amounts are denominated.
        id (int | Unset): Unique identifier for this budget line item. Use as the {id} path parameter for the Show and
            Update endpoints.
        original_budget_amount (float | Unset): Original budgeted amount for this line, before any budget changes.
        quantity (float | Unset): Budgeted quantity in the line's unit of measure. Multiplied by unit_cost when
            calculation_strategy is 'automatic'.
        unit_cost (float | Unset): Cost per unit of measure. Multiplied by quantity when calculation_strategy is
            'automatic'.
        uom (str | Unset): Unit of measure for the line's quantity, such as hours. Any value from the company's
            configured Units of Measure list.
        wbs_code (ProcoreBudgetLineItemWbsCode | Unset): Work Breakdown Structure (WBS) code this line item is budgeted
            against.
    """

    calculation_strategy: str | Unset = UNSET
    currency_configuration: ProcoreBudgetLineItemCurrencyConfiguration | Unset = UNSET
    id: int | Unset = UNSET
    original_budget_amount: float | Unset = UNSET
    quantity: float | Unset = UNSET
    unit_cost: float | Unset = UNSET
    uom: str | Unset = UNSET
    wbs_code: ProcoreBudgetLineItemWbsCode | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        calculation_strategy = self.calculation_strategy

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        id = self.id

        original_budget_amount = self.original_budget_amount

        quantity = self.quantity

        unit_cost = self.unit_cost

        uom = self.uom

        wbs_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.wbs_code, Unset):
            wbs_code = self.wbs_code.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if calculation_strategy is not UNSET:
            field_dict["calculation_strategy"] = calculation_strategy
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if id is not UNSET:
            field_dict["id"] = id
        if original_budget_amount is not UNSET:
            field_dict["original_budget_amount"] = original_budget_amount
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if unit_cost is not UNSET:
            field_dict["unit_cost"] = unit_cost
        if uom is not UNSET:
            field_dict["uom"] = uom
        if wbs_code is not UNSET:
            field_dict["wbs_code"] = wbs_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_budget_line_item_currency_configuration import (
            ProcoreBudgetLineItemCurrencyConfiguration,
        )
        from ..models.procore_budget_line_item_wbs_code import (
            ProcoreBudgetLineItemWbsCode,
        )

        d = dict(src_dict)
        calculation_strategy = d.pop("calculation_strategy", UNSET)

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: ProcoreBudgetLineItemCurrencyConfiguration | Unset
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = (
                ProcoreBudgetLineItemCurrencyConfiguration.from_dict(
                    _currency_configuration
                )
            )

        id = d.pop("id", UNSET)

        original_budget_amount = d.pop("original_budget_amount", UNSET)

        quantity = d.pop("quantity", UNSET)

        unit_cost = d.pop("unit_cost", UNSET)

        uom = d.pop("uom", UNSET)

        _wbs_code = d.pop("wbs_code", UNSET)
        wbs_code: ProcoreBudgetLineItemWbsCode | Unset
        if isinstance(_wbs_code, Unset):
            wbs_code = UNSET
        else:
            wbs_code = ProcoreBudgetLineItemWbsCode.from_dict(_wbs_code)

        procore_budget_line_item = cls(
            calculation_strategy=calculation_strategy,
            currency_configuration=currency_configuration,
            id=id,
            original_budget_amount=original_budget_amount,
            quantity=quantity,
            unit_cost=unit_cost,
            uom=uom,
            wbs_code=wbs_code,
        )

        procore_budget_line_item.additional_properties = d
        return procore_budget_line_item

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
