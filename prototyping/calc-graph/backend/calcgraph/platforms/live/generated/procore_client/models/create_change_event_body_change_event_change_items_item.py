from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_body_change_event_change_items_item_budget_code_type_0 import (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0,
    )
    from ..models.create_change_event_body_change_event_change_items_item_budget_impact import (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpact,
    )
    from ..models.create_change_event_body_change_event_change_items_item_cost_impact import (
        CreateChangeEventBodyChangeEventChangeItemsItemCostImpact,
    )
    from ..models.create_change_event_body_change_event_change_items_item_revenue_impact import (
        CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact,
    )


T = TypeVar("T", bound="CreateChangeEventBodyChangeEventChangeItemsItem")


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItem:
    """
    Attributes:
        budget_code (CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0 | None | Unset): the Budget Code
            associated to the Change Item. If one is not provided, the Change Event Line Item will be created with a 'None'
            Budget Code.
        budget_impact (CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpact | Unset):
        cost_impact (CreateChangeEventBodyChangeEventChangeItemsItemCostImpact | Unset):
        description (str | Unset): Description
        revenue_impact (CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact | Unset):
    """

    budget_code: (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0 | None | Unset
    ) = UNSET
    budget_impact: (
        CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpact | Unset
    ) = UNSET
    cost_impact: CreateChangeEventBodyChangeEventChangeItemsItemCostImpact | Unset = (
        UNSET
    )
    description: str | Unset = UNSET
    revenue_impact: (
        CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_change_event_body_change_event_change_items_item_budget_code_type_0 import (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0,
        )

        budget_code: dict[str, Any] | None | Unset
        if isinstance(self.budget_code, Unset):
            budget_code = UNSET
        elif isinstance(
            self.budget_code,
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0,
        ):
            budget_code = self.budget_code.to_dict()
        else:
            budget_code = self.budget_code

        budget_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.budget_impact, Unset):
            budget_impact = self.budget_impact.to_dict()

        cost_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_impact, Unset):
            cost_impact = self.cost_impact.to_dict()

        description = self.description

        revenue_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.revenue_impact, Unset):
            revenue_impact = self.revenue_impact.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if budget_code is not UNSET:
            field_dict["budget_code"] = budget_code
        if budget_impact is not UNSET:
            field_dict["budget_impact"] = budget_impact
        if cost_impact is not UNSET:
            field_dict["cost_impact"] = cost_impact
        if description is not UNSET:
            field_dict["description"] = description
        if revenue_impact is not UNSET:
            field_dict["revenue_impact"] = revenue_impact

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_body_change_event_change_items_item_budget_code_type_0 import (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0,
        )
        from ..models.create_change_event_body_change_event_change_items_item_budget_impact import (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpact,
        )
        from ..models.create_change_event_body_change_event_change_items_item_cost_impact import (
            CreateChangeEventBodyChangeEventChangeItemsItemCostImpact,
        )
        from ..models.create_change_event_body_change_event_change_items_item_revenue_impact import (
            CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact,
        )

        d = dict(src_dict)

        def _parse_budget_code(
            data: object,
        ) -> (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0
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
                budget_code_type_0 = CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0.from_dict(
                    data
                )

                return budget_code_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventBodyChangeEventChangeItemsItemBudgetCodeType0
                | None
                | Unset,
                data,
            )

        budget_code = _parse_budget_code(d.pop("budget_code", UNSET))

        _budget_impact = d.pop("budget_impact", UNSET)
        budget_impact: (
            CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpact | Unset
        )
        if isinstance(_budget_impact, Unset):
            budget_impact = UNSET
        else:
            budget_impact = (
                CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpact.from_dict(
                    _budget_impact
                )
            )

        _cost_impact = d.pop("cost_impact", UNSET)
        cost_impact: CreateChangeEventBodyChangeEventChangeItemsItemCostImpact | Unset
        if isinstance(_cost_impact, Unset):
            cost_impact = UNSET
        else:
            cost_impact = (
                CreateChangeEventBodyChangeEventChangeItemsItemCostImpact.from_dict(
                    _cost_impact
                )
            )

        description = d.pop("description", UNSET)

        _revenue_impact = d.pop("revenue_impact", UNSET)
        revenue_impact: (
            CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact | Unset
        )
        if isinstance(_revenue_impact, Unset):
            revenue_impact = UNSET
        else:
            revenue_impact = (
                CreateChangeEventBodyChangeEventChangeItemsItemRevenueImpact.from_dict(
                    _revenue_impact
                )
            )

        create_change_event_body_change_event_change_items_item = cls(
            budget_code=budget_code,
            budget_impact=budget_impact,
            cost_impact=cost_impact,
            description=description,
            revenue_impact=revenue_impact,
        )

        create_change_event_body_change_event_change_items_item.additional_properties = d
        return create_change_event_body_change_event_change_items_item

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
