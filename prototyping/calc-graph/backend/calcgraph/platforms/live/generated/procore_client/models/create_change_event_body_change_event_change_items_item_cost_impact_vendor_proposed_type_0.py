from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendorProposedType0",
)


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItemCostImpactVendorProposedType0:
    """the Proposed Vendor associated to the Change Item

    Attributes:
        id (int | Unset): ID
    """

    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        create_change_event_body_change_event_change_items_item_cost_impact_vendor_proposed_type_0 = cls(
            id=id,
        )

        create_change_event_body_change_event_change_items_item_cost_impact_vendor_proposed_type_0.additional_properties = d
        return create_change_event_body_change_event_change_items_item_cost_impact_vendor_proposed_type_0

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
