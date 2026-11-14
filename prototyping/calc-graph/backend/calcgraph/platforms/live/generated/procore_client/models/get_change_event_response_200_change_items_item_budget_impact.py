from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.get_change_event_response_200_change_items_item_budget_impact_source_of_budget_rom import (
    GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfBudgetRom,
)
from ..models.get_change_event_response_200_change_items_item_budget_impact_source_of_latest_budget_impact import (
    GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact,
)
from ..models.get_change_event_response_200_change_items_item_budget_impact_source_of_stage import (
    GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfStage,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_change import (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChange,
    )
    from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification import (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification,
    )
    from ..models.get_change_event_response_200_change_items_item_budget_impact_estimate import (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimate,
    )


T = TypeVar("T", bound="GetChangeEventResponse200ChangeItemsItemBudgetImpact")


@_attrs_define
class GetChangeEventResponse200ChangeItemsItemBudgetImpact:
    """
    Attributes:
        budget_change (GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChange | Unset):
        budget_modification (GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification | Unset):
        estimate (GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimate | Unset):
        source_of_budget_rom (GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfBudgetRom | Unset): Source of
            budget ROM
        source_of_latest_budget_impact (GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact |
            Unset): Source of latest budget impact
        source_of_stage (GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfStage | Unset): The source of the
            stage
    """

    budget_change: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChange | Unset
    ) = UNSET
    budget_modification: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification | Unset
    ) = UNSET
    estimate: GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimate | Unset = (
        UNSET
    )
    source_of_budget_rom: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfBudgetRom | Unset
    ) = UNSET
    source_of_latest_budget_impact: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact
        | Unset
    ) = UNSET
    source_of_stage: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfStage | Unset
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
        from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_change import (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChange,
        )
        from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification import (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification,
        )
        from ..models.get_change_event_response_200_change_items_item_budget_impact_estimate import (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimate,
        )

        d = dict(src_dict)
        _budget_change = d.pop("budget_change", UNSET)
        budget_change: (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChange | Unset
        )
        if isinstance(_budget_change, Unset):
            budget_change = UNSET
        else:
            budget_change = GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetChange.from_dict(
                _budget_change
            )

        _budget_modification = d.pop("budget_modification", UNSET)
        budget_modification: (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification
            | Unset
        )
        if isinstance(_budget_modification, Unset):
            budget_modification = UNSET
        else:
            budget_modification = GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification.from_dict(
                _budget_modification
            )

        _estimate = d.pop("estimate", UNSET)
        estimate: GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimate | Unset
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = (
                GetChangeEventResponse200ChangeItemsItemBudgetImpactEstimate.from_dict(
                    _estimate
                )
            )

        _source_of_budget_rom = d.pop("source_of_budget_rom", UNSET)
        source_of_budget_rom: (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfBudgetRom
            | Unset
        )
        if isinstance(_source_of_budget_rom, Unset):
            source_of_budget_rom = UNSET
        else:
            source_of_budget_rom = (
                GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfBudgetRom(
                    _source_of_budget_rom
                )
            )

        _source_of_latest_budget_impact = d.pop("source_of_latest_budget_impact", UNSET)
        source_of_latest_budget_impact: (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact
            | Unset
        )
        if isinstance(_source_of_latest_budget_impact, Unset):
            source_of_latest_budget_impact = UNSET
        else:
            source_of_latest_budget_impact = GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact(
                _source_of_latest_budget_impact
            )

        _source_of_stage = d.pop("source_of_stage", UNSET)
        source_of_stage: (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfStage | Unset
        )
        if isinstance(_source_of_stage, Unset):
            source_of_stage = UNSET
        else:
            source_of_stage = (
                GetChangeEventResponse200ChangeItemsItemBudgetImpactSourceOfStage(
                    _source_of_stage
                )
            )

        get_change_event_response_200_change_items_item_budget_impact = cls(
            budget_change=budget_change,
            budget_modification=budget_modification,
            estimate=estimate,
            source_of_budget_rom=source_of_budget_rom,
            source_of_latest_budget_impact=source_of_latest_budget_impact,
            source_of_stage=source_of_stage,
        )

        get_change_event_response_200_change_items_item_budget_impact.additional_properties = d
        return get_change_event_response_200_change_items_item_budget_impact

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
