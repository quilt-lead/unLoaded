from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_change_status import (
    CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeStatus,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_change_adjustment_line_item import (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem,
    )


T = TypeVar(
    "T", bound="CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange"
)


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange:
    """
    Attributes:
        adjustment_line_item (CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem |
            Unset):
        days_in_stage (int | Unset): Number of days since Change Event Line Item was associated with Budget Change and
            until Change Event was closed (or until today if it wasn't)
        id (int | Unset): Unique identifier for the Budget Change
        in_status_since (datetime.datetime | None | Unset): Last time this status was updated
        number (int | Unset): Number field of the Budget Change
        status (CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeStatus | Unset): Status of the Budget
            Change
        title (str | Unset): Title of Budget Change
    """

    adjustment_line_item: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem
        | Unset
    ) = UNSET
    days_in_stage: int | Unset = UNSET
    id: int | Unset = UNSET
    in_status_since: datetime.datetime | None | Unset = UNSET
    number: int | Unset = UNSET
    status: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeStatus
        | Unset
    ) = UNSET
    title: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        adjustment_line_item: dict[str, Any] | Unset = UNSET
        if not isinstance(self.adjustment_line_item, Unset):
            adjustment_line_item = self.adjustment_line_item.to_dict()

        days_in_stage = self.days_in_stage

        id = self.id

        in_status_since: None | str | Unset
        if isinstance(self.in_status_since, Unset):
            in_status_since = UNSET
        elif isinstance(self.in_status_since, datetime.datetime):
            in_status_since = self.in_status_since.isoformat()
        else:
            in_status_since = self.in_status_since

        number = self.number

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if adjustment_line_item is not UNSET:
            field_dict["adjustment_line_item"] = adjustment_line_item
        if days_in_stage is not UNSET:
            field_dict["days_in_stage"] = days_in_stage
        if id is not UNSET:
            field_dict["id"] = id
        if in_status_since is not UNSET:
            field_dict["in_status_since"] = in_status_since
        if number is not UNSET:
            field_dict["number"] = number
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_change_adjustment_line_item import (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem,
        )

        d = dict(src_dict)
        _adjustment_line_item = d.pop("adjustment_line_item", UNSET)
        adjustment_line_item: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem
            | Unset
        )
        if isinstance(_adjustment_line_item, Unset):
            adjustment_line_item = UNSET
        else:
            adjustment_line_item = CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeAdjustmentLineItem.from_dict(
                _adjustment_line_item
            )

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

        number = d.pop("number", UNSET)

        _status = d.pop("status", UNSET)
        status: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeStatus
            | Unset
        )
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChangeStatus(
                _status
            )

        title = d.pop("title", UNSET)

        create_change_event_response_201_change_items_item_budget_impact_budget_change = cls(
            adjustment_line_item=adjustment_line_item,
            days_in_stage=days_in_stage,
            id=id,
            in_status_since=in_status_since,
            number=number,
            status=status,
            title=title,
        )

        create_change_event_response_201_change_items_item_budget_impact_budget_change.additional_properties = d
        return create_change_event_response_201_change_items_item_budget_impact_budget_change

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
