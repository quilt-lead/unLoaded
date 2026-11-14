from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.get_change_event_response_200_change_items_item_cost_impact_request_for_quote_type_0_status import (
    GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0Status,
)
from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0"
)


@_attrs_define
class GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0:
    """Request for Quote data if any present, can be null

    Attributes:
        days_in_stage (int | Unset): Number of days since Change Event Line Item was associated with Request For Quote
            and until Change Event was closed (or until today if it wasn't)
        id (int | Unset): Request for Quote ID
        in_status_since (datetime.datetime | None | Unset): Last time this status was updated
        latest_quote_amount (None | str | Unset): Request for Quote latest quote amount if present, can be null
        number (None | str | Unset): Request for quote number
        status (GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0Status | Unset): Request for Quote
            status
        title (None | str | Unset): Request for Quote title
    """

    days_in_stage: int | Unset = UNSET
    id: int | Unset = UNSET
    in_status_since: datetime.datetime | None | Unset = UNSET
    latest_quote_amount: None | str | Unset = UNSET
    number: None | str | Unset = UNSET
    status: (
        GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0Status
        | Unset
    ) = UNSET
    title: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        days_in_stage = self.days_in_stage

        id = self.id

        in_status_since: None | str | Unset
        if isinstance(self.in_status_since, Unset):
            in_status_since = UNSET
        elif isinstance(self.in_status_since, datetime.datetime):
            in_status_since = self.in_status_since.isoformat()
        else:
            in_status_since = self.in_status_since

        latest_quote_amount: None | str | Unset
        if isinstance(self.latest_quote_amount, Unset):
            latest_quote_amount = UNSET
        else:
            latest_quote_amount = self.latest_quote_amount

        number: None | str | Unset
        if isinstance(self.number, Unset):
            number = UNSET
        else:
            number = self.number

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        title: None | str | Unset
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if days_in_stage is not UNSET:
            field_dict["days_in_stage"] = days_in_stage
        if id is not UNSET:
            field_dict["id"] = id
        if in_status_since is not UNSET:
            field_dict["in_status_since"] = in_status_since
        if latest_quote_amount is not UNSET:
            field_dict["latest_quote_amount"] = latest_quote_amount
        if number is not UNSET:
            field_dict["number"] = number
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        days_in_stage = d.pop("days_in_stage", UNSET)

        id = d.pop("id", UNSET)

        def _parse_in_status_since(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                in_status_since_type_0 = datetime.datetime.fromisoformat(data)

                return in_status_since_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        in_status_since = _parse_in_status_since(d.pop("in_status_since", UNSET))

        def _parse_latest_quote_amount(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        latest_quote_amount = _parse_latest_quote_amount(
            d.pop("latest_quote_amount", UNSET)
        )

        def _parse_number(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        number = _parse_number(d.pop("number", UNSET))

        _status = d.pop("status", UNSET)
        status: (
            GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0Status
            | Unset
        )
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = GetChangeEventResponse200ChangeItemsItemCostImpactRequestForQuoteType0Status(
                _status
            )

        def _parse_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title = _parse_title(d.pop("title", UNSET))

        get_change_event_response_200_change_items_item_cost_impact_request_for_quote_type_0 = cls(
            days_in_stage=days_in_stage,
            id=id,
            in_status_since=in_status_since,
            latest_quote_amount=latest_quote_amount,
            number=number,
            status=status,
            title=title,
        )

        get_change_event_response_200_change_items_item_cost_impact_request_for_quote_type_0.additional_properties = d
        return get_change_event_response_200_change_items_item_cost_impact_request_for_quote_type_0

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
