from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code import (
        ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode,
    )


T = TypeVar("T", bound="ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer")


@_attrs_define
class ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransfer:
    """
    Attributes:
        amount (str | Unset): Estimated budget transfer amount
        from_wbs_code (ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode | Unset): Item's
            associated Budget Code
    """

    amount: str | Unset = UNSET
    from_wbs_code: (
        ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        from_wbs_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.from_wbs_code, Unset):
            from_wbs_code = self.from_wbs_code.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if from_wbs_code is not UNSET:
            field_dict["from_wbs_code"] = from_wbs_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_change_items_item_budget_impact_estimate_transfer_from_wbs_code import (
            ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode,
        )

        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        _from_wbs_code = d.pop("from_wbs_code", UNSET)
        from_wbs_code: (
            ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode
            | Unset
        )
        if isinstance(_from_wbs_code, Unset):
            from_wbs_code = UNSET
        else:
            from_wbs_code = ProcoreChangeEventChangeItemsItemBudgetImpactEstimateTransferFromWbsCode.from_dict(
                _from_wbs_code
            )

        procore_change_event_change_items_item_budget_impact_estimate_transfer = cls(
            amount=amount,
            from_wbs_code=from_wbs_code,
        )

        procore_change_event_change_items_item_budget_impact_estimate_transfer.additional_properties = d
        return procore_change_event_change_items_item_budget_impact_estimate_transfer

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
