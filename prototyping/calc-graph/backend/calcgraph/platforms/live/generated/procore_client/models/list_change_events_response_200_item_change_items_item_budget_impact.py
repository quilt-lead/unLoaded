from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_change_events_response_200_item_change_items_item_budget_impact_source_of_budget_rom import (
    ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfBudgetRom,
)
from ..models.list_change_events_response_200_item_change_items_item_budget_impact_source_of_latest_budget_impact import (
    ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact,
)
from ..models.list_change_events_response_200_item_change_items_item_budget_impact_source_of_stage import (
    ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfStage,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_change_events_response_200_item_change_items_item_budget_impact_budget_change import (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetChange,
    )
    from ..models.list_change_events_response_200_item_change_items_item_budget_impact_budget_modification import (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetModification,
    )
    from ..models.list_change_events_response_200_item_change_items_item_budget_impact_estimate import (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimate,
    )


T = TypeVar("T", bound="ListChangeEventsResponse200ItemChangeItemsItemBudgetImpact")


@_attrs_define
class ListChangeEventsResponse200ItemChangeItemsItemBudgetImpact:
    """
    Attributes:
        budget_change (ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetChange | Unset):
        budget_modification (ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetModification | Unset):
        estimate (ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimate | Unset):
        source_of_budget_rom (ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfBudgetRom | Unset):
            Source of budget ROM
        source_of_latest_budget_impact
            (ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact | Unset): Source of latest
            budget impact
        source_of_stage (ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfStage | Unset): The source of
            the stage
    """

    budget_change: (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetChange | Unset
    ) = UNSET
    budget_modification: (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetModification
        | Unset
    ) = UNSET
    estimate: (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimate | Unset
    ) = UNSET
    source_of_budget_rom: (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfBudgetRom
        | Unset
    ) = UNSET
    source_of_latest_budget_impact: (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact
        | Unset
    ) = UNSET
    source_of_stage: (
        ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfStage | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        budget_change: dict[str, Any] | Unset = UNSET
        if not isinstance(self.budget_change, Unset):
            budget_change = self.budget_change.to_dict()

        budget_modification: dict[str, Any] | Unset = UNSET
        if not isinstance(self.budget_modification, Unset):
            budget_modification = self.budget_modification.to_dict()

        estimate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.estimate, Unset):
            estimate = self.estimate.to_dict()

        source_of_budget_rom: str | Unset = UNSET
        if not isinstance(self.source_of_budget_rom, Unset):
            source_of_budget_rom = self.source_of_budget_rom.value

        source_of_latest_budget_impact: str | Unset = UNSET
        if not isinstance(self.source_of_latest_budget_impact, Unset):
            source_of_latest_budget_impact = self.source_of_latest_budget_impact.value

        source_of_stage: str | Unset = UNSET
        if not isinstance(self.source_of_stage, Unset):
            source_of_stage = self.source_of_stage.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if budget_change is not UNSET:
            field_dict["budget_change"] = budget_change
        if budget_modification is not UNSET:
            field_dict["budget_modification"] = budget_modification
        if estimate is not UNSET:
            field_dict["estimate"] = estimate
        if source_of_budget_rom is not UNSET:
            field_dict["source_of_budget_rom"] = source_of_budget_rom
        if source_of_latest_budget_impact is not UNSET:
            field_dict["source_of_latest_budget_impact"] = (
                source_of_latest_budget_impact
            )
        if source_of_stage is not UNSET:
            field_dict["source_of_stage"] = source_of_stage

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_change_events_response_200_item_change_items_item_budget_impact_budget_change import (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetChange,
        )
        from ..models.list_change_events_response_200_item_change_items_item_budget_impact_budget_modification import (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetModification,
        )
        from ..models.list_change_events_response_200_item_change_items_item_budget_impact_estimate import (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimate,
        )

        d = dict(src_dict)
        _budget_change = d.pop("budget_change", UNSET)
        budget_change: (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetChange
            | Unset
        )
        if isinstance(_budget_change, Unset):
            budget_change = UNSET
        else:
            budget_change = ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetChange.from_dict(
                _budget_change
            )

        _budget_modification = d.pop("budget_modification", UNSET)
        budget_modification: (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetModification
            | Unset
        )
        if isinstance(_budget_modification, Unset):
            budget_modification = UNSET
        else:
            budget_modification = ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactBudgetModification.from_dict(
                _budget_modification
            )

        _estimate = d.pop("estimate", UNSET)
        estimate: (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimate | Unset
        )
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactEstimate.from_dict(
                _estimate
            )

        _source_of_budget_rom = d.pop("source_of_budget_rom", UNSET)
        source_of_budget_rom: (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfBudgetRom
            | Unset
        )
        if isinstance(_source_of_budget_rom, Unset):
            source_of_budget_rom = UNSET
        else:
            source_of_budget_rom = ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfBudgetRom(
                _source_of_budget_rom
            )

        _source_of_latest_budget_impact = d.pop("source_of_latest_budget_impact", UNSET)
        source_of_latest_budget_impact: (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact
            | Unset
        )
        if isinstance(_source_of_latest_budget_impact, Unset):
            source_of_latest_budget_impact = UNSET
        else:
            source_of_latest_budget_impact = ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact(
                _source_of_latest_budget_impact
            )

        _source_of_stage = d.pop("source_of_stage", UNSET)
        source_of_stage: (
            ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfStage
            | Unset
        )
        if isinstance(_source_of_stage, Unset):
            source_of_stage = UNSET
        else:
            source_of_stage = (
                ListChangeEventsResponse200ItemChangeItemsItemBudgetImpactSourceOfStage(
                    _source_of_stage
                )
            )

        list_change_events_response_200_item_change_items_item_budget_impact = cls(
            budget_change=budget_change,
            budget_modification=budget_modification,
            estimate=estimate,
            source_of_budget_rom=source_of_budget_rom,
            source_of_latest_budget_impact=source_of_latest_budget_impact,
            source_of_stage=source_of_stage,
        )

        list_change_events_response_200_item_change_items_item_budget_impact.additional_properties = d
        return list_change_events_response_200_item_change_items_item_budget_impact

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
