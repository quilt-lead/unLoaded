from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_change_order_packages_response_200_item_contract_vendor import (
        ListChangeOrderPackagesResponse200ItemContractVendor,
    )


T = TypeVar("T", bound="ListChangeOrderPackagesResponse200ItemContract")


@_attrs_define
class ListChangeOrderPackagesResponse200ItemContract:
    """Contract details including the associated vendor

    Attributes:
        vendor (ListChangeOrderPackagesResponse200ItemContractVendor | Unset): Vendor associated with the contract
    """

    vendor: ListChangeOrderPackagesResponse200ItemContractVendor | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        vendor: dict[str, Any] | Unset = UNSET
        if not isinstance(self.vendor, Unset):
            vendor = self.vendor.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if vendor is not UNSET:
            field_dict["vendor"] = vendor

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_change_order_packages_response_200_item_contract_vendor import (
            ListChangeOrderPackagesResponse200ItemContractVendor,
        )

        d = dict(src_dict)
        _vendor = d.pop("vendor", UNSET)
        vendor: ListChangeOrderPackagesResponse200ItemContractVendor | Unset
        if isinstance(_vendor, Unset):
            vendor = UNSET
        else:
            vendor = ListChangeOrderPackagesResponse200ItemContractVendor.from_dict(
                _vendor
            )

        list_change_order_packages_response_200_item_contract = cls(
            vendor=vendor,
        )

        list_change_order_packages_response_200_item_contract.additional_properties = d
        return list_change_order_packages_response_200_item_contract

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
