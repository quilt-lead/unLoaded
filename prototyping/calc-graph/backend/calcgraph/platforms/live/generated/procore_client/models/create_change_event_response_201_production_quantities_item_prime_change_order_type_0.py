from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_production_quantities_item_prime_change_order_type_0_type import (
    CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0Type,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_production_quantities_item_prime_change_order_type_0_line_item_type_0 import (
        CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0,
    )
    from ..models.create_change_event_response_201_production_quantities_item_prime_change_order_type_0_production_quantity import (
        CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity,
    )


T = TypeVar(
    "T",
    bound="CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0",
)


@_attrs_define
class CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0:
    """prime contract change order data

    Attributes:
        contract_id (int | Unset): Prime Contract ID
        description (str | Unset): Prime PCO description
        id (int | Unset): Package id when type is change_order_package. Potential change order id when type is
            potential_change_order.
        line_item (CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0 | None |
            Unset): Present for 1-tier packages. holder_id is the potential change order id used by the change order show
            page.
        number (int | Unset): Prime PCO number
        production_quantity (CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity
            | Unset): production quantity
        status (str | Unset): Prime PCO status
        title (str | Unset): title
        type_ (CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0Type | Unset): type of change
            order
    """

    contract_id: int | Unset = UNSET
    description: str | Unset = UNSET
    id: int | Unset = UNSET
    line_item: (
        CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0
        | None
        | Unset
    ) = UNSET
    number: int | Unset = UNSET
    production_quantity: (
        CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity
        | Unset
    ) = UNSET
    status: str | Unset = UNSET
    title: str | Unset = UNSET
    type_: (
        CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0Type
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_change_event_response_201_production_quantities_item_prime_change_order_type_0_line_item_type_0 import (
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0,
        )

        contract_id = self.contract_id

        description = self.description

        id = self.id

        line_item: dict[str, Any] | None | Unset
        if isinstance(self.line_item, Unset):
            line_item = UNSET
        elif isinstance(
            self.line_item,
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0,
        ):
            line_item = self.line_item.to_dict()
        else:
            line_item = self.line_item

        number = self.number

        production_quantity: dict[str, Any] | Unset = UNSET
        if not isinstance(self.production_quantity, Unset):
            production_quantity = self.production_quantity.to_dict()

        status = self.status

        title = self.title

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if contract_id is not UNSET:
            field_dict["contract_id"] = contract_id
        if description is not UNSET:
            field_dict["description"] = description
        if id is not UNSET:
            field_dict["id"] = id
        if line_item is not UNSET:
            field_dict["line_item"] = line_item
        if number is not UNSET:
            field_dict["number"] = number
        if production_quantity is not UNSET:
            field_dict["production_quantity"] = production_quantity
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_response_201_production_quantities_item_prime_change_order_type_0_line_item_type_0 import (
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0,
        )
        from ..models.create_change_event_response_201_production_quantities_item_prime_change_order_type_0_production_quantity import (
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity,
        )

        d = dict(src_dict)
        contract_id = d.pop("contract_id", UNSET)

        description = d.pop("description", UNSET)

        id = d.pop("id", UNSET)

        def _parse_line_item(
            data: object,
        ) -> (
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0
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
                line_item_type_0 = CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0.from_dict(
                    data
                )

                return line_item_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0LineItemType0
                | None
                | Unset,
                data,
            )

        line_item = _parse_line_item(d.pop("line_item", UNSET))

        number = d.pop("number", UNSET)

        _production_quantity = d.pop("production_quantity", UNSET)
        production_quantity: (
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity
            | Unset
        )
        if isinstance(_production_quantity, Unset):
            production_quantity = UNSET
        else:
            production_quantity = CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0ProductionQuantity.from_dict(
                _production_quantity
            )

        status = d.pop("status", UNSET)

        title = d.pop("title", UNSET)

        _type_ = d.pop("type", UNSET)
        type_: (
            CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0Type
            | Unset
        )
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = CreateChangeEventResponse201ProductionQuantitiesItemPrimeChangeOrderType0Type(
                _type_
            )

        create_change_event_response_201_production_quantities_item_prime_change_order_type_0 = cls(
            contract_id=contract_id,
            description=description,
            id=id,
            line_item=line_item,
            number=number,
            production_quantity=production_quantity,
            status=status,
            title=title,
            type_=type_,
        )

        create_change_event_response_201_production_quantities_item_prime_change_order_type_0.additional_properties = d
        return create_change_event_response_201_production_quantities_item_prime_change_order_type_0

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
