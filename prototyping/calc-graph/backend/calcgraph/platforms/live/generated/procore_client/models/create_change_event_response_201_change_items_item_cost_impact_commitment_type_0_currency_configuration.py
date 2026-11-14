from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration",
)


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration:
    """Currency configuration information for the Commitment

    Attributes:
        base_currency_iso_code (None | str | Unset): Base currency ISO code (project currency)
        currency_exchange_rate (None | str | Unset): The Commitment Contract or Change Order currency exchange rate to
            project currency
        currency_iso_code (None | str | Unset): Currency ISO code of the Commitment Contract
    """

    base_currency_iso_code: None | str | Unset = UNSET
    currency_exchange_rate: None | str | Unset = UNSET
    currency_iso_code: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        base_currency_iso_code: None | str | Unset
        if isinstance(self.base_currency_iso_code, Unset):
            base_currency_iso_code = UNSET
        else:
            base_currency_iso_code = self.base_currency_iso_code

        currency_exchange_rate: None | str | Unset
        if isinstance(self.currency_exchange_rate, Unset):
            currency_exchange_rate = UNSET
        else:
            currency_exchange_rate = self.currency_exchange_rate

        currency_iso_code: None | str | Unset
        if isinstance(self.currency_iso_code, Unset):
            currency_iso_code = UNSET
        else:
            currency_iso_code = self.currency_iso_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if base_currency_iso_code is not UNSET:
            field_dict["base_currency_iso_code"] = base_currency_iso_code
        if currency_exchange_rate is not UNSET:
            field_dict["currency_exchange_rate"] = currency_exchange_rate
        if currency_iso_code is not UNSET:
            field_dict["currency_iso_code"] = currency_iso_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_base_currency_iso_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        base_currency_iso_code = _parse_base_currency_iso_code(
            d.pop("base_currency_iso_code", UNSET)
        )

        def _parse_currency_exchange_rate(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        currency_exchange_rate = _parse_currency_exchange_rate(
            d.pop("currency_exchange_rate", UNSET)
        )

        def _parse_currency_iso_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        currency_iso_code = _parse_currency_iso_code(d.pop("currency_iso_code", UNSET))

        create_change_event_response_201_change_items_item_cost_impact_commitment_type_0_currency_configuration = cls(
            base_currency_iso_code=base_currency_iso_code,
            currency_exchange_rate=currency_exchange_rate,
            currency_iso_code=currency_iso_code,
        )

        create_change_event_response_201_change_items_item_cost_impact_commitment_type_0_currency_configuration.additional_properties = d
        return create_change_event_response_201_change_items_item_cost_impact_commitment_type_0_currency_configuration

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
