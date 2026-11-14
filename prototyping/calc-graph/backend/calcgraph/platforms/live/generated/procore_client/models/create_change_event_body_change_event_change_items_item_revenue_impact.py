from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_body_change_event_change_items_item_revenue_impact_source_of_revenue_rom import (
    CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_body_change_event_change_items_item_revenue_impact_estimate import (
        CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate,
    )


T = TypeVar("T", bound="CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact")


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact:
    """
    Attributes:
        estimate (CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate | Unset):
        source_of_revenue_rom (CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom | Unset):
            Revenue ROM source for this Change Item
    """

    estimate: (
        CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate | Unset
    ) = UNSET
    source_of_revenue_rom: (
        CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        estimate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.estimate, Unset):
            estimate = self.estimate.to_dict()

        source_of_revenue_rom: str | Unset = UNSET
        if not isinstance(self.source_of_revenue_rom, Unset):
            source_of_revenue_rom = self.source_of_revenue_rom.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if estimate is not UNSET:
            field_dict["estimate"] = estimate
        if source_of_revenue_rom is not UNSET:
            field_dict["source_of_revenue_rom"] = source_of_revenue_rom

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_body_change_event_change_items_item_revenue_impact_estimate import (
            CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate,
        )

        d = dict(src_dict)
        _estimate = d.pop("estimate", UNSET)
        estimate: (
            CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate | Unset
        )
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactEstimate.from_dict(
                _estimate
            )

        _source_of_revenue_rom = d.pop("source_of_revenue_rom", UNSET)
        source_of_revenue_rom: (
            CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom
            | Unset
        )
        if isinstance(_source_of_revenue_rom, Unset):
            source_of_revenue_rom = UNSET
        else:
            source_of_revenue_rom = CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom(
                _source_of_revenue_rom
            )

        create_change_event_body_change_event_change_items_item_revenue_impact = cls(
            estimate=estimate,
            source_of_revenue_rom=source_of_revenue_rom,
        )

        create_change_event_body_change_event_change_items_item_revenue_impact.additional_properties = d
        return create_change_event_body_change_event_change_items_item_revenue_impact

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
