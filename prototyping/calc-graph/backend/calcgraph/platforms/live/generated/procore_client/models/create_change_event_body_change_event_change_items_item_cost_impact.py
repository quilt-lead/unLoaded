from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_body_change_event_change_items_item_cost_impact_contract import (
        CreateChangeEventBodyChangeEventChangeItemsItemCostImpactContract,
    )
    from ..models.create_change_event_body_change_event_change_items_item_cost_impact_estimate import (
        CreateChangeEventBodyChangeEventChangeItemsItemCostImpactEstimate,
    )
    from ..models.create_change_event_body_change_event_change_items_item_cost_impact_vendor import (
        CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendor,
    )


T = TypeVar("T", bound="CreateChangeEventBodyChangeEventChangeItemsItemCostImpact")


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItemCostImpact:
    """
    Attributes:
        contract (CreateChangeEventBodyChangeEventChangeItemsItemCostImpactContract | Unset):
        estimate (CreateChangeEventBodyChangeEventChangeItemsItemCostImpactEstimate | Unset):
        vendor (CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendor | Unset):
    """

    contract: (
        CreateChangeEventBodyChangeEventChangeItemsItemCostImpactContract | Unset
    ) = UNSET
    estimate: (
        CreateChangeEventBodyChangeEventChangeItemsItemCostImpactEstimate | Unset
    ) = UNSET
    vendor: CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendor | Unset = (
        UNSET
    )
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        contract: dict[str, Any] | Unset = UNSET
        if not isinstance(self.contract, Unset):
            contract = self.contract.to_dict()

        estimate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.estimate, Unset):
            estimate = self.estimate.to_dict()

        vendor: dict[str, Any] | Unset = UNSET
        if not isinstance(self.vendor, Unset):
            vendor = self.vendor.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if contract is not UNSET:
            field_dict["contract"] = contract
        if estimate is not UNSET:
            field_dict["estimate"] = estimate
        if vendor is not UNSET:
            field_dict["vendor"] = vendor

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_body_change_event_change_items_item_cost_impact_contract import (
            CreateChangeEventBodyChangeEventChangeItemsItemCostImpactContract,
        )
        from ..models.create_change_event_body_change_event_change_items_item_cost_impact_estimate import (
            CreateChangeEventBodyChangeEventChangeItemsItemCostImpactEstimate,
        )
        from ..models.create_change_event_body_change_event_change_items_item_cost_impact_vendor import (
            CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendor,
        )

        d = dict(src_dict)
        _contract = d.pop("contract", UNSET)
        contract: (
            CreateChangeEventBodyChangeEventChangeItemsItemCostImpactContract | Unset
        )
        if isinstance(_contract, Unset):
            contract = UNSET
        else:
            contract = CreateChangeEventBodyChangeEventChangeItemsItemCostImpactContract.from_dict(
                _contract
            )

        _estimate = d.pop("estimate", UNSET)
        estimate: (
            CreateChangeEventBodyChangeEventChangeItemsItemCostImpactEstimate | Unset
        )
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = CreateChangeEventBodyChangeEventChangeItemsItemCostImpactEstimate.from_dict(
                _estimate
            )

        _vendor = d.pop("vendor", UNSET)
        vendor: CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendor | Unset
        if isinstance(_vendor, Unset):
            vendor = UNSET
        else:
            vendor = CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendor.from_dict(
                _vendor
            )

        create_change_event_body_change_event_change_items_item_cost_impact = cls(
            contract=contract,
            estimate=estimate,
            vendor=vendor,
        )

        create_change_event_body_change_event_change_items_item_cost_impact.additional_properties = d
        return create_change_event_body_change_event_change_items_item_cost_impact

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
