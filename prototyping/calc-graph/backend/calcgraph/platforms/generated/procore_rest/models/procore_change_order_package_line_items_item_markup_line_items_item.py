from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_order_package_line_items_item_markup_line_items_item_currency_configuration import (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemCurrencyConfiguration,
    )
    from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup import (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup,
    )


T = TypeVar("T", bound="ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem")


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem:
    """
    Attributes:
        amount (str | Unset): Markup Line Item amount
        created_at (datetime.datetime | Unset): Created at
        currency_configuration (ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemCurrencyConfiguration | Unset):
        id (int | Unset): Markup Line Item ID
        markup (ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup | Unset):
        updated_at (datetime.datetime | Unset): Updated at
    """

    amount: str | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    currency_configuration: (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemCurrencyConfiguration
        | Unset
    ) = UNSET
    id: int | Unset = UNSET
    markup: ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup | Unset = (
        UNSET
    )
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        amount = self.amount

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        id = self.id

        markup: dict[str, Any] | Unset = UNSET
        if not isinstance(self.markup, Unset):
            markup = self.markup.to_dict()

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if amount is not UNSET:
            field_dict["amount"] = amount
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if id is not UNSET:
            field_dict["id"] = id
        if markup is not UNSET:
            field_dict["markup"] = markup
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_order_package_line_items_item_markup_line_items_item_currency_configuration import (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemCurrencyConfiguration,
        )
        from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup import (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup,
        )

        d = dict(src_dict)
        amount = d.pop("amount", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemCurrencyConfiguration
            | Unset
        )
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemCurrencyConfiguration.from_dict(
                _currency_configuration
            )

        id = d.pop("id", UNSET)

        _markup = d.pop("markup", UNSET)
        markup: ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup | Unset
        if isinstance(_markup, Unset):
            markup = UNSET
        else:
            markup = ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup.from_dict(
                _markup
            )

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        procore_change_order_package_line_items_item_markup_line_items_item = cls(
            amount=amount,
            created_at=created_at,
            currency_configuration=currency_configuration,
            id=id,
            markup=markup,
            updated_at=updated_at,
        )

        procore_change_order_package_line_items_item_markup_line_items_item.additional_properties = d
        return procore_change_order_package_line_items_item_markup_line_items_item

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
