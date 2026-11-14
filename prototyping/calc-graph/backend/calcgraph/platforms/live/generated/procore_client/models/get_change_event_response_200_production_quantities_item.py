from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_change_event_response_200_production_quantities_item_budget_change_type_0 import (
        GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0,
    )
    from ..models.get_change_event_response_200_production_quantities_item_estimate import (
        GetChangeEventResponse200ProductionQuantitiesItemEstimate,
    )
    from ..models.get_change_event_response_200_production_quantities_item_prime_change_order_type_0 import (
        GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0,
    )
    from ..models.get_change_event_response_200_production_quantities_item_production_code import (
        GetChangeEventResponse200ProductionQuantitiesItemProductionCode,
    )


T = TypeVar("T", bound="GetChangeEventResponse200ProductionQuantitiesItem")


@_attrs_define
class GetChangeEventResponse200ProductionQuantitiesItem:
    """
    Attributes:
        budget_change (GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0 | None | Unset): budget change
        disabled_fields (list[str] | Unset): array of disabled fields for production quantities
        estimate (GetChangeEventResponse200ProductionQuantitiesItemEstimate | Unset): production quantity estimate
        event_id (int | Unset): production quantity event id
        id (int | Unset): production quantity id
        item_type (str | Unset): item type
        prime_change_order (GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0 | None | Unset):
            prime contract change order data
        production_code (GetChangeEventResponse200ProductionQuantitiesItemProductionCode | Unset): production quantity
            cost code and if enabled sub job data
    """

    budget_change: (
        GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0
        | None
        | Unset
    ) = UNSET
    disabled_fields: list[str] | Unset = UNSET
    estimate: GetChangeEventResponse200ProductionQuantitiesItemEstimate | Unset = UNSET
    event_id: int | Unset = UNSET
    id: int | Unset = UNSET
    item_type: str | Unset = UNSET
    prime_change_order: (
        GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0
        | None
        | Unset
    ) = UNSET
    production_code: (
        GetChangeEventResponse200ProductionQuantitiesItemProductionCode | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.get_change_event_response_200_production_quantities_item_budget_change_type_0 import (
            GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0,
        )
        from ..models.get_change_event_response_200_production_quantities_item_prime_change_order_type_0 import (
            GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0,
        )

        budget_change: dict[str, Any] | None | Unset
        if isinstance(self.budget_change, Unset):
            budget_change = UNSET
        elif isinstance(
            self.budget_change,
            GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0,
        ):
            budget_change = self.budget_change.to_dict()
        else:
            budget_change = self.budget_change

        disabled_fields: list[str] | Unset = UNSET
        if not isinstance(self.disabled_fields, Unset):
            disabled_fields = self.disabled_fields

        estimate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.estimate, Unset):
            estimate = self.estimate.to_dict()

        event_id = self.event_id

        id = self.id

        item_type = self.item_type

        prime_change_order: dict[str, Any] | None | Unset
        if isinstance(self.prime_change_order, Unset):
            prime_change_order = UNSET
        elif isinstance(
            self.prime_change_order,
            GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0,
        ):
            prime_change_order = self.prime_change_order.to_dict()
        else:
            prime_change_order = self.prime_change_order

        production_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.production_code, Unset):
            production_code = self.production_code.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if budget_change is not UNSET:
            field_dict["budget_change"] = budget_change
        if disabled_fields is not UNSET:
            field_dict["disabled_fields"] = disabled_fields
        if estimate is not UNSET:
            field_dict["estimate"] = estimate
        if event_id is not UNSET:
            field_dict["event_id"] = event_id
        if id is not UNSET:
            field_dict["id"] = id
        if item_type is not UNSET:
            field_dict["item_type"] = item_type
        if prime_change_order is not UNSET:
            field_dict["prime_change_order"] = prime_change_order
        if production_code is not UNSET:
            field_dict["production_code"] = production_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.get_change_event_response_200_production_quantities_item_budget_change_type_0 import (
            GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0,
        )
        from ..models.get_change_event_response_200_production_quantities_item_estimate import (
            GetChangeEventResponse200ProductionQuantitiesItemEstimate,
        )
        from ..models.get_change_event_response_200_production_quantities_item_prime_change_order_type_0 import (
            GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0,
        )
        from ..models.get_change_event_response_200_production_quantities_item_production_code import (
            GetChangeEventResponse200ProductionQuantitiesItemProductionCode,
        )

        d = dict(src_dict)

        def _parse_budget_change(
            data: object,
        ) -> (
            GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0
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
                budget_change_type_0 = GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0.from_dict(
                    data
                )

                return budget_change_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                GetChangeEventResponse200ProductionQuantitiesItemBudgetChangeType0
                | None
                | Unset,
                data,
            )

        budget_change = _parse_budget_change(d.pop("budget_change", UNSET))

        disabled_fields = cast(list[str], d.pop("disabled_fields", UNSET))

        _estimate = d.pop("estimate", UNSET)
        estimate: GetChangeEventResponse200ProductionQuantitiesItemEstimate | Unset
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = (
                GetChangeEventResponse200ProductionQuantitiesItemEstimate.from_dict(
                    _estimate
                )
            )

        event_id = d.pop("event_id", UNSET)

        id = d.pop("id", UNSET)

        item_type = d.pop("item_type", UNSET)

        def _parse_prime_change_order(
            data: object,
        ) -> (
            GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0
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
                prime_change_order_type_0 = GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0.from_dict(
                    data
                )

                return prime_change_order_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                GetChangeEventResponse200ProductionQuantitiesItemPrimeChangeOrderType0
                | None
                | Unset,
                data,
            )

        prime_change_order = _parse_prime_change_order(
            d.pop("prime_change_order", UNSET)
        )

        _production_code = d.pop("production_code", UNSET)
        production_code: (
            GetChangeEventResponse200ProductionQuantitiesItemProductionCode | Unset
        )
        if isinstance(_production_code, Unset):
            production_code = UNSET
        else:
            production_code = GetChangeEventResponse200ProductionQuantitiesItemProductionCode.from_dict(
                _production_code
            )

        get_change_event_response_200_production_quantities_item = cls(
            budget_change=budget_change,
            disabled_fields=disabled_fields,
            estimate=estimate,
            event_id=event_id,
            id=id,
            item_type=item_type,
            prime_change_order=prime_change_order,
            production_code=production_code,
        )

        get_change_event_response_200_production_quantities_item.additional_properties = d
        return get_change_event_response_200_production_quantities_item

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
