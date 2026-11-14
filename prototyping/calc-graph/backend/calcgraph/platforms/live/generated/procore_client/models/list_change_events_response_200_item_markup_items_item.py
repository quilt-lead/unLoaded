from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_change_events_response_200_item_markup_items_item_revenue import (
        ListChangeEventsResponse200ItemMarkupItemsItemRevenue,
    )
    from ..models.list_change_events_response_200_item_markup_items_item_wbs_code import (
        ListChangeEventsResponse200ItemMarkupItemsItemWbsCode,
    )


T = TypeVar("T", bound="ListChangeEventsResponse200ItemMarkupItemsItem")


@_attrs_define
class ListChangeEventsResponse200ItemMarkupItemsItem:
    """
    Attributes:
        event_id (int | Unset): markup item's change event id
        id (str | Unset): markup item ID
        item_type (str | Unset): item type
        revenue (ListChangeEventsResponse200ItemMarkupItemsItemRevenue | Unset): markup item revenue summary
        wbs_code (ListChangeEventsResponse200ItemMarkupItemsItemWbsCode | Unset): Item's associated Budget Code
    """

    event_id: int | Unset = UNSET
    id: str | Unset = UNSET
    item_type: str | Unset = UNSET
    revenue: ListChangeEventsResponse200ItemMarkupItemsItemRevenue | Unset = UNSET
    wbs_code: ListChangeEventsResponse200ItemMarkupItemsItemWbsCode | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        event_id = self.event_id

        id = self.id

        item_type = self.item_type

        revenue: dict[str, Any] | Unset = UNSET
        if not isinstance(self.revenue, Unset):
            revenue = self.revenue.to_dict()

        wbs_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.wbs_code, Unset):
            wbs_code = self.wbs_code.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if event_id is not UNSET:
            field_dict["event_id"] = event_id
        if id is not UNSET:
            field_dict["id"] = id
        if item_type is not UNSET:
            field_dict["item_type"] = item_type
        if revenue is not UNSET:
            field_dict["revenue"] = revenue
        if wbs_code is not UNSET:
            field_dict["wbs_code"] = wbs_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_change_events_response_200_item_markup_items_item_revenue import (
            ListChangeEventsResponse200ItemMarkupItemsItemRevenue,
        )
        from ..models.list_change_events_response_200_item_markup_items_item_wbs_code import (
            ListChangeEventsResponse200ItemMarkupItemsItemWbsCode,
        )

        d = dict(src_dict)
        event_id = d.pop("event_id", UNSET)

        id = d.pop("id", UNSET)

        item_type = d.pop("item_type", UNSET)

        _revenue = d.pop("revenue", UNSET)
        revenue: ListChangeEventsResponse200ItemMarkupItemsItemRevenue | Unset
        if isinstance(_revenue, Unset):
            revenue = UNSET
        else:
            revenue = ListChangeEventsResponse200ItemMarkupItemsItemRevenue.from_dict(
                _revenue
            )

        _wbs_code = d.pop("wbs_code", UNSET)
        wbs_code: ListChangeEventsResponse200ItemMarkupItemsItemWbsCode | Unset
        if isinstance(_wbs_code, Unset):
            wbs_code = UNSET
        else:
            wbs_code = ListChangeEventsResponse200ItemMarkupItemsItemWbsCode.from_dict(
                _wbs_code
            )

        list_change_events_response_200_item_markup_items_item = cls(
            event_id=event_id,
            id=id,
            item_type=item_type,
            revenue=revenue,
            wbs_code=wbs_code,
        )

        list_change_events_response_200_item_markup_items_item.additional_properties = d
        return list_change_events_response_200_item_markup_items_item

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
