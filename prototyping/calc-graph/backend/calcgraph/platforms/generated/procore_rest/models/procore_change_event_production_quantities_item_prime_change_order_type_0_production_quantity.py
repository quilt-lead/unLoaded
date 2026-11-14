from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ProcoreChangeEventProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity",
)


@_attrs_define
class ProcoreChangeEventProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity:
    """production quantity

    Attributes:
        id (int | Unset): Prime PCO production quantity id
        quantity (str | Unset): quantity of Prime PCO production quantity
        unit_of_measure (str | Unset): Prime PCO production quantity unit of measure
    """

    id: int | Unset = UNSET
    quantity: str | Unset = UNSET
    unit_of_measure: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        quantity = self.quantity

        unit_of_measure = self.unit_of_measure

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if unit_of_measure is not UNSET:
            field_dict["unit_of_measure"] = unit_of_measure

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        quantity = d.pop("quantity", UNSET)

        unit_of_measure = d.pop("unit_of_measure", UNSET)

        procore_change_event_production_quantities_item_prime_change_order_type_0_production_quantity = cls(
            id=id,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
        )

        procore_change_event_production_quantities_item_prime_change_order_type_0_production_quantity.additional_properties = d
        return procore_change_event_production_quantities_item_prime_change_order_type_0_production_quantity

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
