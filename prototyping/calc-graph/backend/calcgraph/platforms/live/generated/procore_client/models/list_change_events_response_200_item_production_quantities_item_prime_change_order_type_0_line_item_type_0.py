from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="ListChangeEventsResponse200ItemProductionQuantitiesItemPrimeChangeOrderType0LineItemType0",
)


@_attrs_define
class ListChangeEventsResponse200ItemProductionQuantitiesItemPrimeChangeOrderType0LineItemType0:
    """Present for 1-tier packages. holder_id is the potential change order id used by the change order show page.

    Attributes:
        holder_id (int | Unset): Potential change order id
    """

    holder_id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        holder_id = self.holder_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if holder_id is not UNSET:
            field_dict["holder_id"] = holder_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        holder_id = d.pop("holder_id", UNSET)

        list_change_events_response_200_item_production_quantities_item_prime_change_order_type_0_line_item_type_0 = cls(
            holder_id=holder_id,
        )

        list_change_events_response_200_item_production_quantities_item_prime_change_order_type_0_line_item_type_0.additional_properties = d
        return list_change_events_response_200_item_production_quantities_item_prime_change_order_type_0_line_item_type_0

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
