from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_from_type_0 import (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0,
    )
    from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_to import (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferTo,
    )


T = TypeVar(
    "T", bound="GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification"
)


@_attrs_define
class GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModification:
    """
    Attributes:
        amount (str | Unset): Amount of budget transferred by this modification, as a decimal string in the project
            currency. Equal to the transfer_amount supplied on the request.
        budget_modification_id (int | Unset): Deprecated. No longer returned by the create endpoint; retained only for
            backwards compatibility and will be removed in a future revision.
        notes (None | str | Unset): Free-text notes describing why the budget transfer was made. Null when no notes were
            provided on creation.
        transfer_from (GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0 | None |
            Unset): Source Budget (Line Item) Code the amount was transferred from. Null when the modification has no source
            line item.
        transfer_to (GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferTo | Unset): Target
            Budget (Line Item) Code the amount was transferred to.
    """

    amount: str | Unset = UNSET
    budget_modification_id: int | Unset = UNSET
    notes: None | str | Unset = UNSET
    transfer_from: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0
        | None
        | Unset
    ) = UNSET
    transfer_to: (
        GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferTo
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_from_type_0 import (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0,
        )

        amount = self.amount

        budget_modification_id = self.budget_modification_id

        notes: None | str | Unset
        if isinstance(self.notes, Unset):
            notes = UNSET
        else:
            notes = self.notes

        transfer_from: dict[str, Any] | None | Unset
        if isinstance(self.transfer_from, Unset):
            transfer_from = UNSET
        elif isinstance(
            self.transfer_from,
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0,
        ):
            transfer_from = self.transfer_from.to_dict()
        else:
            transfer_from = self.transfer_from

        transfer_to: dict[str, Any] | Unset = UNSET
        if not isinstance(self.transfer_to, Unset):
            transfer_to = self.transfer_to.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if budget_modification_id is not UNSET:
            field_dict["budget_modification_id"] = budget_modification_id
        if notes is not UNSET:
            field_dict["notes"] = notes
        if transfer_from is not UNSET:
            field_dict["transfer_from"] = transfer_from
        if transfer_to is not UNSET:
            field_dict["transfer_to"] = transfer_to

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_from_type_0 import (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0,
        )
        from ..models.get_change_event_response_200_change_items_item_budget_impact_budget_modification_transfer_to import (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferTo,
        )

        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        budget_modification_id = d.pop("budget_modification_id", UNSET)

        def _parse_notes(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        notes = _parse_notes(d.pop("notes", UNSET))

        def _parse_transfer_from(
            data: object,
        ) -> (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0
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
                transfer_from_type_0 = GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0.from_dict(
                    data
                )

                return transfer_from_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferFromType0
                | None
                | Unset,
                data,
            )

        transfer_from = _parse_transfer_from(d.pop("transfer_from", UNSET))

        _transfer_to = d.pop("transfer_to", UNSET)
        transfer_to: (
            GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferTo
            | Unset
        )
        if isinstance(_transfer_to, Unset):
            transfer_to = UNSET
        else:
            transfer_to = GetChangeEventResponse200ChangeItemsItemBudgetImpactBudgetModificationTransferTo.from_dict(
                _transfer_to
            )

        get_change_event_response_200_change_items_item_budget_impact_budget_modification = cls(
            amount=amount,
            budget_modification_id=budget_modification_id,
            notes=notes,
            transfer_from=transfer_from,
            transfer_to=transfer_to,
        )

        get_change_event_response_200_change_items_item_budget_impact_budget_modification.additional_properties = d
        return get_change_event_response_200_change_items_item_budget_impact_budget_modification

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
