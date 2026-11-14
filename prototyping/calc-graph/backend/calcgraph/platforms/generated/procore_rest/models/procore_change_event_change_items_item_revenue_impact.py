from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.procore_change_event_change_items_item_revenue_impact_source_of_latest_price import (
    ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfLatestPrice,
)
from ..models.procore_change_event_change_items_item_revenue_impact_source_of_revenue_rom import (
    ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom,
)
from ..models.procore_change_event_change_items_item_revenue_impact_source_of_stage import (
    ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfStage,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_change_items_item_revenue_impact_change_order_package_type_0 import (
        ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0,
    )
    from ..models.procore_change_event_change_items_item_revenue_impact_change_order_type_0 import (
        ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0,
    )
    from ..models.procore_change_event_change_items_item_revenue_impact_estimate import (
        ProcoreChangeEventChangeItemsItemRevenueImpactEstimate,
    )


T = TypeVar("T", bound="ProcoreChangeEventChangeItemsItemRevenueImpact")


@_attrs_define
class ProcoreChangeEventChangeItemsItemRevenueImpact:
    """
    Attributes:
        change_order (None | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0 | Unset):
        change_order_package (None | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0 | Unset):
        estimate (ProcoreChangeEventChangeItemsItemRevenueImpactEstimate | Unset):
        source_of_latest_price (ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfLatestPrice | Unset): Latest price
            source
        source_of_revenue_rom (ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom | Unset): Revenue ROM
            source
        source_of_stage (ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfStage | Unset): Source of the stage
    """

    change_order: (
        None | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0 | Unset
    ) = UNSET
    change_order_package: (
        None
        | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0
        | Unset
    ) = UNSET
    estimate: ProcoreChangeEventChangeItemsItemRevenueImpactEstimate | Unset = UNSET
    source_of_latest_price: (
        ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfLatestPrice | Unset
    ) = UNSET
    source_of_revenue_rom: (
        ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom | Unset
    ) = UNSET
    source_of_stage: (
        ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfStage | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.procore_change_event_change_items_item_revenue_impact_change_order_package_type_0 import (
            ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0,
        )
        from ..models.procore_change_event_change_items_item_revenue_impact_change_order_type_0 import (
            ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0,
        )

        change_order: dict[str, Any] | None | Unset
        if isinstance(self.change_order, Unset):
            change_order = UNSET
        elif isinstance(
            self.change_order,
            ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0,
        ):
            change_order = self.change_order.to_dict()
        else:
            change_order = self.change_order

        change_order_package: dict[str, Any] | None | Unset
        if isinstance(self.change_order_package, Unset):
            change_order_package = UNSET
        elif isinstance(
            self.change_order_package,
            ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0,
        ):
            change_order_package = self.change_order_package.to_dict()
        else:
            change_order_package = self.change_order_package

        estimate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.estimate, Unset):
            estimate = self.estimate.to_dict()

        source_of_latest_price: str | Unset = UNSET
        if not isinstance(self.source_of_latest_price, Unset):
            source_of_latest_price = self.source_of_latest_price.value

        source_of_revenue_rom: str | Unset = UNSET
        if not isinstance(self.source_of_revenue_rom, Unset):
            source_of_revenue_rom = self.source_of_revenue_rom.value

        source_of_stage: str | Unset = UNSET
        if not isinstance(self.source_of_stage, Unset):
            source_of_stage = self.source_of_stage.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if change_order is not UNSET:
            field_dict["change_order"] = change_order
        if change_order_package is not UNSET:
            field_dict["change_order_package"] = change_order_package
        if estimate is not UNSET:
            field_dict["estimate"] = estimate
        if source_of_latest_price is not UNSET:
            field_dict["source_of_latest_price"] = source_of_latest_price
        if source_of_revenue_rom is not UNSET:
            field_dict["source_of_revenue_rom"] = source_of_revenue_rom
        if source_of_stage is not UNSET:
            field_dict["source_of_stage"] = source_of_stage

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_change_items_item_revenue_impact_change_order_package_type_0 import (
            ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0,
        )
        from ..models.procore_change_event_change_items_item_revenue_impact_change_order_type_0 import (
            ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0,
        )
        from ..models.procore_change_event_change_items_item_revenue_impact_estimate import (
            ProcoreChangeEventChangeItemsItemRevenueImpactEstimate,
        )

        d = dict(src_dict)

        def _parse_change_order(
            data: object,
        ) -> (
            None
            | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_order_type_0 = ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0.from_dict(
                    data
                )

                return change_order_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                None
                | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderType0
                | Unset,
                data,
            )

        change_order = _parse_change_order(d.pop("change_order", UNSET))

        def _parse_change_order_package(
            data: object,
        ) -> (
            None
            | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_order_package_type_0 = ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0.from_dict(
                    data
                )

                return change_order_package_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                None
                | ProcoreChangeEventChangeItemsItemRevenueImpactChangeOrderPackageType0
                | Unset,
                data,
            )

        change_order_package = _parse_change_order_package(
            d.pop("change_order_package", UNSET)
        )

        _estimate = d.pop("estimate", UNSET)
        estimate: ProcoreChangeEventChangeItemsItemRevenueImpactEstimate | Unset
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = ProcoreChangeEventChangeItemsItemRevenueImpactEstimate.from_dict(
                _estimate
            )

        _source_of_latest_price = d.pop("source_of_latest_price", UNSET)
        source_of_latest_price: (
            ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfLatestPrice | Unset
        )
        if isinstance(_source_of_latest_price, Unset):
            source_of_latest_price = UNSET
        else:
            source_of_latest_price = (
                ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfLatestPrice(
                    _source_of_latest_price
                )
            )

        _source_of_revenue_rom = d.pop("source_of_revenue_rom", UNSET)
        source_of_revenue_rom: (
            ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom | Unset
        )
        if isinstance(_source_of_revenue_rom, Unset):
            source_of_revenue_rom = UNSET
        else:
            source_of_revenue_rom = (
                ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfRevenueRom(
                    _source_of_revenue_rom
                )
            )

        _source_of_stage = d.pop("source_of_stage", UNSET)
        source_of_stage: (
            ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfStage | Unset
        )
        if isinstance(_source_of_stage, Unset):
            source_of_stage = UNSET
        else:
            source_of_stage = (
                ProcoreChangeEventChangeItemsItemRevenueImpactSourceOfStage(
                    _source_of_stage
                )
            )

        procore_change_event_change_items_item_revenue_impact = cls(
            change_order=change_order,
            change_order_package=change_order_package,
            estimate=estimate,
            source_of_latest_price=source_of_latest_price,
            source_of_revenue_rom=source_of_revenue_rom,
            source_of_stage=source_of_stage,
        )

        procore_change_event_change_items_item_revenue_impact.additional_properties = d
        return procore_change_event_change_items_item_revenue_impact

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
