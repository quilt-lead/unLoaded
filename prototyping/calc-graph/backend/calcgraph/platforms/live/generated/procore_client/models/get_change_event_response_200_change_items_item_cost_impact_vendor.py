from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_change_event_response_200_change_items_item_cost_impact_vendor_confirmed_type_0 import (
        GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0,
    )
    from ..models.get_change_event_response_200_change_items_item_cost_impact_vendor_proposed_type_0 import (
        GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0,
    )


T = TypeVar("T", bound="GetChangeEventResponse200ChangeItemsItemCostImpactVendor")


@_attrs_define
class GetChangeEventResponse200ChangeItemsItemCostImpactVendor:
    """
    Attributes:
        confirmed (GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0 | None | Unset): The Confirmed
            Vendor associated to the Change Item
        proposed (GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0 | None | Unset): the Proposed
            Vendor associated to the Change Item
    """

    confirmed: (
        GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0
        | None
        | Unset
    ) = UNSET
    proposed: (
        GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0
        | None
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.get_change_event_response_200_change_items_item_cost_impact_vendor_confirmed_type_0 import (
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0,
        )
        from ..models.get_change_event_response_200_change_items_item_cost_impact_vendor_proposed_type_0 import (
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0,
        )

        confirmed: dict[str, Any] | None | Unset
        if isinstance(self.confirmed, Unset):
            confirmed = UNSET
        elif isinstance(
            self.confirmed,
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0,
        ):
            confirmed = self.confirmed.to_dict()
        else:
            confirmed = self.confirmed

        proposed: dict[str, Any] | None | Unset
        if isinstance(self.proposed, Unset):
            proposed = UNSET
        elif isinstance(
            self.proposed,
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0,
        ):
            proposed = self.proposed.to_dict()
        else:
            proposed = self.proposed

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if confirmed is not UNSET:
            field_dict["confirmed"] = confirmed
        if proposed is not UNSET:
            field_dict["proposed"] = proposed

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.get_change_event_response_200_change_items_item_cost_impact_vendor_confirmed_type_0 import (
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0,
        )
        from ..models.get_change_event_response_200_change_items_item_cost_impact_vendor_proposed_type_0 import (
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0,
        )

        d = dict(src_dict)

        def _parse_confirmed(
            data: object,
        ) -> (
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0
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
                confirmed_type_0 = GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0.from_dict(
                    data
                )

                return confirmed_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                GetChangeEventResponse200ChangeItemsItemCostImpactVendorConfirmedType0
                | None
                | Unset,
                data,
            )

        confirmed = _parse_confirmed(d.pop("confirmed", UNSET))

        def _parse_proposed(
            data: object,
        ) -> (
            GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0
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
                proposed_type_0 = GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0.from_dict(
                    data
                )

                return proposed_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                GetChangeEventResponse200ChangeItemsItemCostImpactVendorProposedType0
                | None
                | Unset,
                data,
            )

        proposed = _parse_proposed(d.pop("proposed", UNSET))

        get_change_event_response_200_change_items_item_cost_impact_vendor = cls(
            confirmed=confirmed,
            proposed=proposed,
        )

        get_change_event_response_200_change_items_item_cost_impact_vendor.additional_properties = d
        return get_change_event_response_200_change_items_item_cost_impact_vendor

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
