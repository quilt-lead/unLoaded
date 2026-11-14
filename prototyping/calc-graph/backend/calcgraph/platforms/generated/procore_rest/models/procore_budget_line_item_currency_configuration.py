from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ProcoreBudgetLineItemCurrencyConfiguration")


@_attrs_define
class ProcoreBudgetLineItemCurrencyConfiguration:
    """Currency in which this line item's monetary amounts are denominated.

    Attributes:
        currency_iso_code (str | Unset): ISO 4217 currency code for the line item's amounts.
    """

    currency_iso_code: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        currency_iso_code = self.currency_iso_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if currency_iso_code is not UNSET:
            field_dict["currency_iso_code"] = currency_iso_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        currency_iso_code = d.pop("currency_iso_code", UNSET)

        procore_budget_line_item_currency_configuration = cls(
            currency_iso_code=currency_iso_code,
        )

        procore_budget_line_item_currency_configuration.additional_properties = d
        return procore_budget_line_item_currency_configuration

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
