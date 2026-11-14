from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_order_package_line_items_item_compact import (
        ProcoreChangeOrderPackageLineItemsItemCompact,
    )
    from ..models.procore_change_order_package_line_items_item_currency_configuration import (
        ProcoreChangeOrderPackageLineItemsItemCurrencyConfiguration,
    )
    from ..models.procore_change_order_package_line_items_item_holder import (
        ProcoreChangeOrderPackageLineItemsItemHolder,
    )
    from ..models.procore_change_order_package_line_items_item_line_item_type import (
        ProcoreChangeOrderPackageLineItemsItemLineItemType,
    )
    from ..models.procore_change_order_package_line_items_item_markup_line_items_item import (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem,
    )
    from ..models.procore_change_order_package_line_items_item_wbs_code import (
        ProcoreChangeOrderPackageLineItemsItemWbsCode,
    )


T = TypeVar("T", bound="ProcoreChangeOrderPackageLineItemsItem")


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItem:
    """
    Attributes:
        cost_code (ProcoreChangeOrderPackageLineItemsItemCompact | Unset):
        currency_configuration (ProcoreChangeOrderPackageLineItemsItemCurrencyConfiguration | Unset):
        description (str | Unset): Description
        extended_amount (str | Unset): Extended amount
        holder (ProcoreChangeOrderPackageLineItemsItemHolder | Unset): Holder
        id (int | Unset): ID
        line_item_type (ProcoreChangeOrderPackageLineItemsItemLineItemType | Unset): Line Item Type
        markup_line_items (list[ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem] | Unset):
        position (int | Unset): Position
        quantity (str | Unset): Quantity
        total_amount (str | Unset): Total amount
        unit_cost (str | Unset): Unit cost
        uom (str | Unset): Unit of measurement
        wbs_code (ProcoreChangeOrderPackageLineItemsItemWbsCode | Unset):
    """

    cost_code: ProcoreChangeOrderPackageLineItemsItemCompact | Unset = UNSET
    currency_configuration: (
        ProcoreChangeOrderPackageLineItemsItemCurrencyConfiguration | Unset
    ) = UNSET
    description: str | Unset = UNSET
    extended_amount: str | Unset = UNSET
    holder: ProcoreChangeOrderPackageLineItemsItemHolder | Unset = UNSET
    id: int | Unset = UNSET
    line_item_type: ProcoreChangeOrderPackageLineItemsItemLineItemType | Unset = UNSET
    markup_line_items: (
        list[ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem] | Unset
    ) = UNSET
    position: int | Unset = UNSET
    quantity: str | Unset = UNSET
    total_amount: str | Unset = UNSET
    unit_cost: str | Unset = UNSET
    uom: str | Unset = UNSET
    wbs_code: ProcoreChangeOrderPackageLineItemsItemWbsCode | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        cost_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_code, Unset):
            cost_code = self.cost_code.to_dict()

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        description = self.description

        extended_amount = self.extended_amount

        holder: dict[str, Any] | Unset = UNSET
        if not isinstance(self.holder, Unset):
            holder = self.holder.to_dict()

        id = self.id

        line_item_type: dict[str, Any] | Unset = UNSET
        if not isinstance(self.line_item_type, Unset):
            line_item_type = self.line_item_type.to_dict()

        markup_line_items: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.markup_line_items, Unset):
            markup_line_items = []
            for markup_line_items_item_data in self.markup_line_items:
                markup_line_items_item = markup_line_items_item_data.to_dict()
                markup_line_items.append(markup_line_items_item)

        position = self.position

        quantity = self.quantity

        total_amount = self.total_amount

        unit_cost = self.unit_cost

        uom = self.uom

        wbs_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.wbs_code, Unset):
            wbs_code = self.wbs_code.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if cost_code is not UNSET:
            field_dict["cost_code"] = cost_code
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if description is not UNSET:
            field_dict["description"] = description
        if extended_amount is not UNSET:
            field_dict["extended_amount"] = extended_amount
        if holder is not UNSET:
            field_dict["holder"] = holder
        if id is not UNSET:
            field_dict["id"] = id
        if line_item_type is not UNSET:
            field_dict["line_item_type"] = line_item_type
        if markup_line_items is not UNSET:
            field_dict["markup_line_items"] = markup_line_items
        if position is not UNSET:
            field_dict["position"] = position
        if quantity is not UNSET:
            field_dict["quantity"] = quantity
        if total_amount is not UNSET:
            field_dict["total_amount"] = total_amount
        if unit_cost is not UNSET:
            field_dict["unit_cost"] = unit_cost
        if uom is not UNSET:
            field_dict["uom"] = uom
        if wbs_code is not UNSET:
            field_dict["wbs_code"] = wbs_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_order_package_line_items_item_compact import (
            ProcoreChangeOrderPackageLineItemsItemCompact,
        )
        from ..models.procore_change_order_package_line_items_item_currency_configuration import (
            ProcoreChangeOrderPackageLineItemsItemCurrencyConfiguration,
        )
        from ..models.procore_change_order_package_line_items_item_holder import (
            ProcoreChangeOrderPackageLineItemsItemHolder,
        )
        from ..models.procore_change_order_package_line_items_item_line_item_type import (
            ProcoreChangeOrderPackageLineItemsItemLineItemType,
        )
        from ..models.procore_change_order_package_line_items_item_markup_line_items_item import (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem,
        )
        from ..models.procore_change_order_package_line_items_item_wbs_code import (
            ProcoreChangeOrderPackageLineItemsItemWbsCode,
        )

        d = dict(src_dict)
        _cost_code = d.pop("cost_code", UNSET)
        cost_code: ProcoreChangeOrderPackageLineItemsItemCompact | Unset
        if isinstance(_cost_code, Unset):
            cost_code = UNSET
        else:
            cost_code = ProcoreChangeOrderPackageLineItemsItemCompact.from_dict(
                _cost_code
            )

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: (
            ProcoreChangeOrderPackageLineItemsItemCurrencyConfiguration | Unset
        )
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = (
                ProcoreChangeOrderPackageLineItemsItemCurrencyConfiguration.from_dict(
                    _currency_configuration
                )
            )

        description = d.pop("description", UNSET)

        extended_amount = d.pop("extended_amount", UNSET)

        _holder = d.pop("holder", UNSET)
        holder: ProcoreChangeOrderPackageLineItemsItemHolder | Unset
        if isinstance(_holder, Unset):
            holder = UNSET
        else:
            holder = ProcoreChangeOrderPackageLineItemsItemHolder.from_dict(_holder)

        id = d.pop("id", UNSET)

        _line_item_type = d.pop("line_item_type", UNSET)
        line_item_type: ProcoreChangeOrderPackageLineItemsItemLineItemType | Unset
        if isinstance(_line_item_type, Unset):
            line_item_type = UNSET
        else:
            line_item_type = (
                ProcoreChangeOrderPackageLineItemsItemLineItemType.from_dict(
                    _line_item_type
                )
            )

        _markup_line_items = d.pop("markup_line_items", UNSET)
        markup_line_items: (
            list[ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem] | Unset
        ) = UNSET
        if _markup_line_items is not UNSET:
            markup_line_items = []
            for markup_line_items_item_data in _markup_line_items:
                markup_line_items_item = (
                    ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItem.from_dict(
                        markup_line_items_item_data
                    )
                )

                markup_line_items.append(markup_line_items_item)

        position = d.pop("position", UNSET)

        quantity = d.pop("quantity", UNSET)

        total_amount = d.pop("total_amount", UNSET)

        unit_cost = d.pop("unit_cost", UNSET)

        uom = d.pop("uom", UNSET)

        _wbs_code = d.pop("wbs_code", UNSET)
        wbs_code: ProcoreChangeOrderPackageLineItemsItemWbsCode | Unset
        if isinstance(_wbs_code, Unset):
            wbs_code = UNSET
        else:
            wbs_code = ProcoreChangeOrderPackageLineItemsItemWbsCode.from_dict(
                _wbs_code
            )

        procore_change_order_package_line_items_item = cls(
            cost_code=cost_code,
            currency_configuration=currency_configuration,
            description=description,
            extended_amount=extended_amount,
            holder=holder,
            id=id,
            line_item_type=line_item_type,
            markup_line_items=markup_line_items,
            position=position,
            quantity=quantity,
            total_amount=total_amount,
            unit_cost=unit_cost,
            uom=uom,
            wbs_code=wbs_code,
        )

        procore_change_order_package_line_items_item.additional_properties = d
        return procore_change_order_package_line_items_item

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
