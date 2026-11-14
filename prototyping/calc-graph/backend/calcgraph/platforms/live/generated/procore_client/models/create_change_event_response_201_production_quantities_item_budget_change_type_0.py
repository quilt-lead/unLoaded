from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_production_quantities_item_budget_change_type_0_production_quantity import (
        CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0ProductionQuantity,
    )


T = TypeVar(
    "T", bound="CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0"
)


@_attrs_define
class CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0:
    """budget change

    Attributes:
        description (str | Unset): budget change description
        id (int | Unset): budget change id
        number (int | Unset): budget change number
        production_quantity (CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0ProductionQuantity |
            Unset): production quantity
        status (str | Unset): budget change status
        title (str | Unset): title
    """

    description: str | Unset = UNSET
    id: int | Unset = UNSET
    number: int | Unset = UNSET
    production_quantity: (
        CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0ProductionQuantity
        | Unset
    ) = UNSET
    status: str | Unset = UNSET
    title: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        description = self.description

        id = self.id

        number = self.number

        production_quantity: dict[str, Any] | Unset = UNSET
        if not isinstance(self.production_quantity, Unset):
            production_quantity = self.production_quantity.to_dict()

        status = self.status

        title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if description is not UNSET:
            field_dict["description"] = description
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number
        if production_quantity is not UNSET:
            field_dict["production_quantity"] = production_quantity
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_response_201_production_quantities_item_budget_change_type_0_production_quantity import (
            CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0ProductionQuantity,
        )

        d = dict(src_dict)
        description = d.pop("description", UNSET)

        id = d.pop("id", UNSET)

        number = d.pop("number", UNSET)

        _production_quantity = d.pop("production_quantity", UNSET)
        production_quantity: (
            CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0ProductionQuantity
            | Unset
        )
        if isinstance(_production_quantity, Unset):
            production_quantity = UNSET
        else:
            production_quantity = CreateChangeEventResponse201ProductionQuantitiesItemBudgetChangeType0ProductionQuantity.from_dict(
                _production_quantity
            )

        status = d.pop("status", UNSET)

        title = d.pop("title", UNSET)

        create_change_event_response_201_production_quantities_item_budget_change_type_0 = cls(
            description=description,
            id=id,
            number=number,
            production_quantity=production_quantity,
            status=status,
            title=title,
        )

        create_change_event_response_201_production_quantities_item_budget_change_type_0.additional_properties = d
        return create_change_event_response_201_production_quantities_item_budget_change_type_0

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
