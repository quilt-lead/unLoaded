from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.procore_change_event_change_items_item_source import (
    ProcoreChangeEventChangeItemsItemSource,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_change_items_item_budget_code import (
        ProcoreChangeEventChangeItemsItemBudgetCode,
    )
    from ..models.procore_change_event_change_items_item_budget_impact import (
        ProcoreChangeEventChangeItemsItemBudgetImpact,
    )
    from ..models.procore_change_event_change_items_item_cost_impact import (
        ProcoreChangeEventChangeItemsItemCostImpact,
    )
    from ..models.procore_change_event_change_items_item_currency_configuration import (
        ProcoreChangeEventChangeItemsItemCurrencyConfiguration,
    )
    from ..models.procore_change_event_change_items_item_latest_cost_values import (
        ProcoreChangeEventChangeItemsItemLatestCostValues,
    )
    from ..models.procore_change_event_change_items_item_latest_revenue_values import (
        ProcoreChangeEventChangeItemsItemLatestRevenueValues,
    )
    from ..models.procore_change_event_change_items_item_notes import (
        ProcoreChangeEventChangeItemsItemNotes,
    )
    from ..models.procore_change_event_change_items_item_revenue_impact import (
        ProcoreChangeEventChangeItemsItemRevenueImpact,
    )


T = TypeVar("T", bound="ProcoreChangeEventChangeItemsItem")


@_attrs_define
class ProcoreChangeEventChangeItemsItem:
    """
    Attributes:
        budget_code (ProcoreChangeEventChangeItemsItemBudgetCode | Unset): Item's associated Budget Code
        budget_impact (ProcoreChangeEventChangeItemsItemBudgetImpact | Unset):
        cost_impact (ProcoreChangeEventChangeItemsItemCostImpact | Unset):
        created_at (datetime.datetime | Unset): Timestamp of when the Change Event Line Item was created
        currency_configuration (ProcoreChangeEventChangeItemsItemCurrencyConfiguration | Unset): Currency configuration
            information
        deletable (bool | Unset): Whether the Line Item is deletable
        deleted_at (datetime.datetime | Unset): Timestamp of when the Line Item was deleted
        description (str | Unset): Description of the Line Item
        editable (bool | Unset): Whether the Line Item is editable
        event_id (int | Unset): The ID of the associated Change Event
        event_number (str | Unset): The number of the associated Change Event
        event_title (str | Unset): The title of the associated Change Event
        id (int | Unset): The ID of the Line Item
        item_type (str | Unset): The type of the Line Item
        latest_cost_values (ProcoreChangeEventChangeItemsItemLatestCostValues | Unset):
        latest_revenue_values (ProcoreChangeEventChangeItemsItemLatestRevenueValues | Unset):
        line_aging (int | Unset): Number of days since Change Event Line Item was added to Change Event and until the
            time the Change Event closed (or until today)
        notes (ProcoreChangeEventChangeItemsItemNotes | Unset): After successful update independent actions may be
            executed. For example: sync WBS code. The failures of those actions will be aggregated under attribute :notes
            and will not result in a Failure.
        revenue_impact (ProcoreChangeEventChangeItemsItemRevenueImpact | Unset):
        source (ProcoreChangeEventChangeItemsItemSource | Unset): Source of Change Item
        updated_at (datetime.datetime | Unset): Timestamp of when the Change Event Line Item was updated
    """

    budget_code: ProcoreChangeEventChangeItemsItemBudgetCode | Unset = UNSET
    budget_impact: ProcoreChangeEventChangeItemsItemBudgetImpact | Unset = UNSET
    cost_impact: ProcoreChangeEventChangeItemsItemCostImpact | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    currency_configuration: (
        ProcoreChangeEventChangeItemsItemCurrencyConfiguration | Unset
    ) = UNSET
    deletable: bool | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    description: str | Unset = UNSET
    editable: bool | Unset = UNSET
    event_id: int | Unset = UNSET
    event_number: str | Unset = UNSET
    event_title: str | Unset = UNSET
    id: int | Unset = UNSET
    item_type: str | Unset = UNSET
    latest_cost_values: ProcoreChangeEventChangeItemsItemLatestCostValues | Unset = (
        UNSET
    )
    latest_revenue_values: (
        ProcoreChangeEventChangeItemsItemLatestRevenueValues | Unset
    ) = UNSET
    line_aging: int | Unset = UNSET
    notes: ProcoreChangeEventChangeItemsItemNotes | Unset = UNSET
    revenue_impact: ProcoreChangeEventChangeItemsItemRevenueImpact | Unset = UNSET
    source: ProcoreChangeEventChangeItemsItemSource | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        budget_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.budget_code, Unset):
            budget_code = self.budget_code.to_dict()

        budget_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.budget_impact, Unset):
            budget_impact = self.budget_impact.to_dict()

        cost_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_impact, Unset):
            cost_impact = self.cost_impact.to_dict()

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        deletable = self.deletable

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        description = self.description

        editable = self.editable

        event_id = self.event_id

        event_number = self.event_number

        event_title = self.event_title

        id = self.id

        item_type = self.item_type

        latest_cost_values: dict[str, Any] | Unset = UNSET
        if not isinstance(self.latest_cost_values, Unset):
            latest_cost_values = self.latest_cost_values.to_dict()

        latest_revenue_values: dict[str, Any] | Unset = UNSET
        if not isinstance(self.latest_revenue_values, Unset):
            latest_revenue_values = self.latest_revenue_values.to_dict()

        line_aging = self.line_aging

        notes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.notes, Unset):
            notes = self.notes.to_dict()

        revenue_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.revenue_impact, Unset):
            revenue_impact = self.revenue_impact.to_dict()

        source: str | Unset = UNSET
        if not isinstance(self.source, Unset):
            source = self.source.value

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if budget_code is not UNSET:
            field_dict["budget_code"] = budget_code
        if budget_impact is not UNSET:
            field_dict["budget_impact"] = budget_impact
        if cost_impact is not UNSET:
            field_dict["cost_impact"] = cost_impact
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if deletable is not UNSET:
            field_dict["deletable"] = deletable
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if description is not UNSET:
            field_dict["description"] = description
        if editable is not UNSET:
            field_dict["editable"] = editable
        if event_id is not UNSET:
            field_dict["event_id"] = event_id
        if event_number is not UNSET:
            field_dict["event_number"] = event_number
        if event_title is not UNSET:
            field_dict["event_title"] = event_title
        if id is not UNSET:
            field_dict["id"] = id
        if item_type is not UNSET:
            field_dict["item_type"] = item_type
        if latest_cost_values is not UNSET:
            field_dict["latest_cost_values"] = latest_cost_values
        if latest_revenue_values is not UNSET:
            field_dict["latest_revenue_values"] = latest_revenue_values
        if line_aging is not UNSET:
            field_dict["line_aging"] = line_aging
        if notes is not UNSET:
            field_dict["notes"] = notes
        if revenue_impact is not UNSET:
            field_dict["revenue_impact"] = revenue_impact
        if source is not UNSET:
            field_dict["source"] = source
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_change_items_item_budget_code import (
            ProcoreChangeEventChangeItemsItemBudgetCode,
        )
        from ..models.procore_change_event_change_items_item_budget_impact import (
            ProcoreChangeEventChangeItemsItemBudgetImpact,
        )
        from ..models.procore_change_event_change_items_item_cost_impact import (
            ProcoreChangeEventChangeItemsItemCostImpact,
        )
        from ..models.procore_change_event_change_items_item_currency_configuration import (
            ProcoreChangeEventChangeItemsItemCurrencyConfiguration,
        )
        from ..models.procore_change_event_change_items_item_latest_cost_values import (
            ProcoreChangeEventChangeItemsItemLatestCostValues,
        )
        from ..models.procore_change_event_change_items_item_latest_revenue_values import (
            ProcoreChangeEventChangeItemsItemLatestRevenueValues,
        )
        from ..models.procore_change_event_change_items_item_notes import (
            ProcoreChangeEventChangeItemsItemNotes,
        )
        from ..models.procore_change_event_change_items_item_revenue_impact import (
            ProcoreChangeEventChangeItemsItemRevenueImpact,
        )

        d = dict(src_dict)
        _budget_code = d.pop("budget_code", UNSET)
        budget_code: ProcoreChangeEventChangeItemsItemBudgetCode | Unset
        if isinstance(_budget_code, Unset):
            budget_code = UNSET
        else:
            budget_code = ProcoreChangeEventChangeItemsItemBudgetCode.from_dict(
                _budget_code
            )

        _budget_impact = d.pop("budget_impact", UNSET)
        budget_impact: ProcoreChangeEventChangeItemsItemBudgetImpact | Unset
        if isinstance(_budget_impact, Unset):
            budget_impact = UNSET
        else:
            budget_impact = ProcoreChangeEventChangeItemsItemBudgetImpact.from_dict(
                _budget_impact
            )

        _cost_impact = d.pop("cost_impact", UNSET)
        cost_impact: ProcoreChangeEventChangeItemsItemCostImpact | Unset
        if isinstance(_cost_impact, Unset):
            cost_impact = UNSET
        else:
            cost_impact = ProcoreChangeEventChangeItemsItemCostImpact.from_dict(
                _cost_impact
            )

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: (
            ProcoreChangeEventChangeItemsItemCurrencyConfiguration | Unset
        )
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = (
                ProcoreChangeEventChangeItemsItemCurrencyConfiguration.from_dict(
                    _currency_configuration
                )
            )

        deletable = d.pop("deletable", UNSET)

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        description = d.pop("description", UNSET)

        editable = d.pop("editable", UNSET)

        event_id = d.pop("event_id", UNSET)

        event_number = d.pop("event_number", UNSET)

        event_title = d.pop("event_title", UNSET)

        id = d.pop("id", UNSET)

        item_type = d.pop("item_type", UNSET)

        _latest_cost_values = d.pop("latest_cost_values", UNSET)
        latest_cost_values: ProcoreChangeEventChangeItemsItemLatestCostValues | Unset
        if isinstance(_latest_cost_values, Unset):
            latest_cost_values = UNSET
        else:
            latest_cost_values = (
                ProcoreChangeEventChangeItemsItemLatestCostValues.from_dict(
                    _latest_cost_values
                )
            )

        _latest_revenue_values = d.pop("latest_revenue_values", UNSET)
        latest_revenue_values: (
            ProcoreChangeEventChangeItemsItemLatestRevenueValues | Unset
        )
        if isinstance(_latest_revenue_values, Unset):
            latest_revenue_values = UNSET
        else:
            latest_revenue_values = (
                ProcoreChangeEventChangeItemsItemLatestRevenueValues.from_dict(
                    _latest_revenue_values
                )
            )

        line_aging = d.pop("line_aging", UNSET)

        _notes = d.pop("notes", UNSET)
        notes: ProcoreChangeEventChangeItemsItemNotes | Unset
        if isinstance(_notes, Unset):
            notes = UNSET
        else:
            notes = ProcoreChangeEventChangeItemsItemNotes.from_dict(_notes)

        _revenue_impact = d.pop("revenue_impact", UNSET)
        revenue_impact: ProcoreChangeEventChangeItemsItemRevenueImpact | Unset
        if isinstance(_revenue_impact, Unset):
            revenue_impact = UNSET
        else:
            revenue_impact = ProcoreChangeEventChangeItemsItemRevenueImpact.from_dict(
                _revenue_impact
            )

        _source = d.pop("source", UNSET)
        source: ProcoreChangeEventChangeItemsItemSource | Unset
        if isinstance(_source, Unset):
            source = UNSET
        else:
            source = ProcoreChangeEventChangeItemsItemSource(_source)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        procore_change_event_change_items_item = cls(
            budget_code=budget_code,
            budget_impact=budget_impact,
            cost_impact=cost_impact,
            created_at=created_at,
            currency_configuration=currency_configuration,
            deletable=deletable,
            deleted_at=deleted_at,
            description=description,
            editable=editable,
            event_id=event_id,
            event_number=event_number,
            event_title=event_title,
            id=id,
            item_type=item_type,
            latest_cost_values=latest_cost_values,
            latest_revenue_values=latest_revenue_values,
            line_aging=line_aging,
            notes=notes,
            revenue_impact=revenue_impact,
            source=source,
            updated_at=updated_at,
        )

        procore_change_event_change_items_item.additional_properties = d
        return procore_change_event_change_items_item

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
