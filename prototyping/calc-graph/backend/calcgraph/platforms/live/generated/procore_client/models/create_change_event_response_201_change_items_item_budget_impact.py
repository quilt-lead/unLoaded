from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_budget_impact_source_of_budget_rom import (
    CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfBudgetRom,
)
from ..models.create_change_event_response_201_change_items_item_budget_impact_source_of_latest_budget_impact import (
    CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact,
)
from ..models.create_change_event_response_201_change_items_item_budget_impact_source_of_stage import (
    CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfStage,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_change import (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange,
    )
    from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_modification import (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetModification,
    )
    from ..models.create_change_event_response_201_change_items_item_budget_impact_estimate import (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactEstimate,
    )


T = TypeVar("T", bound="CreateChangeEventResponse201ChangeItemsItemBudgetImpact")


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemBudgetImpact:
    """
    Attributes:
        budget_change (CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange | Unset):
        budget_modification (CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetModification | Unset):
        estimate (CreateChangeEventResponse201ChangeItemsItemBudgetImpactEstimate | Unset):
        source_of_budget_rom (CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfBudgetRom | Unset): Source
            of budget ROM
        source_of_latest_budget_impact
            (CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact | Unset): Source of latest
            budget impact
        source_of_stage (CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfStage | Unset): The source of
            the stage
    """

    budget_change: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange | Unset
    ) = UNSET
    budget_modification: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetModification
        | Unset
    ) = UNSET
    estimate: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactEstimate | Unset
    ) = UNSET
    source_of_budget_rom: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfBudgetRom | Unset
    ) = UNSET
    source_of_latest_budget_impact: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact
        | Unset
    ) = UNSET
    source_of_stage: (
        CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfStage | Unset
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
        from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_change import (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange,
        )
        from ..models.create_change_event_response_201_change_items_item_budget_impact_budget_modification import (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetModification,
        )
        from ..models.create_change_event_response_201_change_items_item_budget_impact_estimate import (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactEstimate,
        )

        d = dict(src_dict)
        _budget_change = d.pop("budget_change", UNSET)
        budget_change: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange | Unset
        )
        if isinstance(_budget_change, Unset):
            budget_change = UNSET
        else:
            budget_change = CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetChange.from_dict(
                _budget_change
            )

        _budget_modification = d.pop("budget_modification", UNSET)
        budget_modification: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetModification
            | Unset
        )
        if isinstance(_budget_modification, Unset):
            budget_modification = UNSET
        else:
            budget_modification = CreateChangeEventResponse201ChangeItemsItemBudgetImpactBudgetModification.from_dict(
                _budget_modification
            )

        _estimate = d.pop("estimate", UNSET)
        estimate: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactEstimate | Unset
        )
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = CreateChangeEventResponse201ChangeItemsItemBudgetImpactEstimate.from_dict(
                _estimate
            )

        _source_of_budget_rom = d.pop("source_of_budget_rom", UNSET)
        source_of_budget_rom: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfBudgetRom
            | Unset
        )
        if isinstance(_source_of_budget_rom, Unset):
            source_of_budget_rom = UNSET
        else:
            source_of_budget_rom = CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfBudgetRom(
                _source_of_budget_rom
            )

        _source_of_latest_budget_impact = d.pop("source_of_latest_budget_impact", UNSET)
        source_of_latest_budget_impact: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact
            | Unset
        )
        if isinstance(_source_of_latest_budget_impact, Unset):
            source_of_latest_budget_impact = UNSET
        else:
            source_of_latest_budget_impact = CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfLatestBudgetImpact(
                _source_of_latest_budget_impact
            )

        _source_of_stage = d.pop("source_of_stage", UNSET)
        source_of_stage: (
            CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfStage | Unset
        )
        if isinstance(_source_of_stage, Unset):
            source_of_stage = UNSET
        else:
            source_of_stage = (
                CreateChangeEventResponse201ChangeItemsItemBudgetImpactSourceOfStage(
                    _source_of_stage
                )
            )

        create_change_event_response_201_change_items_item_budget_impact = cls(
            budget_change=budget_change,
            budget_modification=budget_modification,
            estimate=estimate,
            source_of_budget_rom=source_of_budget_rom,
            source_of_latest_budget_impact=source_of_latest_budget_impact,
            source_of_stage=source_of_stage,
        )

        create_change_event_response_201_change_items_item_budget_impact.additional_properties = d
        return create_change_event_response_201_change_items_item_budget_impact

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
