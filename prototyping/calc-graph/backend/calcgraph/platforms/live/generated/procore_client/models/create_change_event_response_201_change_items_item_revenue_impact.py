from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_revenue_impact_source_of_latest_price import (
    CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfLatestPrice,
)
from ..models.create_change_event_response_201_change_items_item_revenue_impact_source_of_revenue_rom import (
    CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfRevenueRom,
)
from ..models.create_change_event_response_201_change_items_item_revenue_impact_source_of_stage import (
    CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfStage,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_change_items_item_revenue_impact_change_order_package_type_0 import (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0,
    )
    from ..models.create_change_event_response_201_change_items_item_revenue_impact_change_order_type_0 import (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0,
    )
    from ..models.create_change_event_response_201_change_items_item_revenue_impact_estimate import (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactEstimate,
    )


T = TypeVar("T", bound="CreateChangeEventResponse201ChangeItemsItemRevenueImpact")


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemRevenueImpact:
    """
    Attributes:
        change_order (CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0 | None | Unset):
        change_order_package (CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0 | None |
            Unset):
        estimate (CreateChangeEventResponse201ChangeItemsItemRevenueImpactEstimate | Unset):
        source_of_latest_price (CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfLatestPrice | Unset):
            Latest price source
        source_of_revenue_rom (CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfRevenueRom | Unset):
            Revenue ROM source
        source_of_stage (CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfStage | Unset): Source of the
            stage
    """

    change_order: (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0
        | None
        | Unset
    ) = UNSET
    change_order_package: (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0
        | None
        | Unset
    ) = UNSET
    estimate: (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactEstimate | Unset
    ) = UNSET
    source_of_latest_price: (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfLatestPrice
        | Unset
    ) = UNSET
    source_of_revenue_rom: (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfRevenueRom
        | Unset
    ) = UNSET
    source_of_stage: (
        CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfStage | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_change_event_response_201_change_items_item_revenue_impact_change_order_package_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0,
        )
        from ..models.create_change_event_response_201_change_items_item_revenue_impact_change_order_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0,
        )

        change_order: dict[str, Any] | None | Unset
        if isinstance(self.change_order, Unset):
            change_order = UNSET
        elif isinstance(
            self.change_order,
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0,
        ):
            change_order = self.change_order.to_dict()
        else:
            change_order = self.change_order

        change_order_package: dict[str, Any] | None | Unset
        if isinstance(self.change_order_package, Unset):
            change_order_package = UNSET
        elif isinstance(
            self.change_order_package,
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0,
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
        from ..models.create_change_event_response_201_change_items_item_revenue_impact_change_order_package_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0,
        )
        from ..models.create_change_event_response_201_change_items_item_revenue_impact_change_order_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0,
        )
        from ..models.create_change_event_response_201_change_items_item_revenue_impact_estimate import (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactEstimate,
        )

        d = dict(src_dict)

        def _parse_change_order(
            data: object,
        ) -> (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_order_type_0 = CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0.from_dict(
                    data
                )

                return change_order_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderType0
                | None
                | Unset,
                data,
            )

        change_order = _parse_change_order(d.pop("change_order", UNSET))

        def _parse_change_order_package(
            data: object,
        ) -> (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_order_package_type_0 = CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0.from_dict(
                    data
                )

                return change_order_package_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventResponse201ChangeItemsItemRevenueImpactChangeOrderPackageType0
                | None
                | Unset,
                data,
            )

        change_order_package = _parse_change_order_package(
            d.pop("change_order_package", UNSET)
        )

        _estimate = d.pop("estimate", UNSET)
        estimate: (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactEstimate | Unset
        )
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = CreateChangeEventResponse201ChangeItemsItemRevenueImpactEstimate.from_dict(
                _estimate
            )

        _source_of_latest_price = d.pop("source_of_latest_price", UNSET)
        source_of_latest_price: (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfLatestPrice
            | Unset
        )
        if isinstance(_source_of_latest_price, Unset):
            source_of_latest_price = UNSET
        else:
            source_of_latest_price = CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfLatestPrice(
                _source_of_latest_price
            )

        _source_of_revenue_rom = d.pop("source_of_revenue_rom", UNSET)
        source_of_revenue_rom: (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfRevenueRom
            | Unset
        )
        if isinstance(_source_of_revenue_rom, Unset):
            source_of_revenue_rom = UNSET
        else:
            source_of_revenue_rom = CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfRevenueRom(
                _source_of_revenue_rom
            )

        _source_of_stage = d.pop("source_of_stage", UNSET)
        source_of_stage: (
            CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfStage
            | Unset
        )
        if isinstance(_source_of_stage, Unset):
            source_of_stage = UNSET
        else:
            source_of_stage = (
                CreateChangeEventResponse201ChangeItemsItemRevenueImpactSourceOfStage(
                    _source_of_stage
                )
            )

        create_change_event_response_201_change_items_item_revenue_impact = cls(
            change_order=change_order,
            change_order_package=change_order_package,
            estimate=estimate,
            source_of_latest_price=source_of_latest_price,
            source_of_revenue_rom=source_of_revenue_rom,
            source_of_stage=source_of_stage,
        )

        create_change_event_response_201_change_items_item_revenue_impact.additional_properties = d
        return create_change_event_response_201_change_items_item_revenue_impact

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
