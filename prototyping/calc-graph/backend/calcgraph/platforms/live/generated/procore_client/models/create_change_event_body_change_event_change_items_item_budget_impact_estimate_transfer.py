from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer",
)


@_attrs_define
class CreateChangeEventBodyChangeEventChangeItemsItemBudgetImpactEstimateTransfer:
    """
    Attributes:
        amount (float | None | Unset): the estimated budget rom transfer amount
        from_wbs_code_id (int | None | Unset): the unique identifier for wbs code from which estimatd budget rom
            transfer will be balanced
    """

    amount: float | None | Unset = UNSET
    from_wbs_code_id: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount: float | None | Unset
        if isinstance(self.amount, Unset):
            amount = UNSET
        else:
            amount = self.amount

        from_wbs_code_id: int | None | Unset
        if isinstance(self.from_wbs_code_id, Unset):
            from_wbs_code_id = UNSET
        else:
            from_wbs_code_id = self.from_wbs_code_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if from_wbs_code_id is not UNSET:
            field_dict["from_wbs_code_id"] = from_wbs_code_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_amount(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        amount = _parse_amount(d.pop("amount", UNSET))

        def _parse_from_wbs_code_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        from_wbs_code_id = _parse_from_wbs_code_id(d.pop("from_wbs_code_id", UNSET))

        create_change_event_body_change_event_change_items_item_budget_impact_estimate_transfer = cls(
            amount=amount,
            from_wbs_code_id=from_wbs_code_id,
        )

        create_change_event_body_change_event_change_items_item_budget_impact_estimate_transfer.additional_properties = d
        return create_change_event_body_change_event_change_items_item_budget_impact_estimate_transfer

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
