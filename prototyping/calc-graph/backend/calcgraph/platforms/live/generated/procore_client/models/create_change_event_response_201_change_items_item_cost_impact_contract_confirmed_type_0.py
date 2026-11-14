from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_cost_impact_contract_confirmed_type_0_contract_type import (
    CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0ContractType,
)
from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0",
)


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0:
    """the Confirmed Contract associated to the Change Item

    Attributes:
        contract_type (CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0ContractType | Unset):
            The type of the Confirmed Contract
        id (int | Unset): Confirmed Contract ID
        number (None | str | Unset): The number of the Confirmed Contract
        status (str | Unset): The status of the Confirmed Contract
        title (None | str | Unset): The title of the Confirmed Contract
    """

    contract_type: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0ContractType
        | Unset
    ) = UNSET
    id: int | Unset = UNSET
    number: None | str | Unset = UNSET
    status: str | Unset = UNSET
    title: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        contract_type: str | Unset = UNSET
        if not isinstance(self.contract_type, Unset):
            contract_type = self.contract_type.value

        id = self.id

        number: None | str | Unset
        if isinstance(self.number, Unset):
            number = UNSET
        else:
            number = self.number

        status = self.status

        title: None | str | Unset
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if contract_type is not UNSET:
            field_dict["contract_type"] = contract_type
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _contract_type = d.pop("contract_type", UNSET)
        contract_type: (
            CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0ContractType
            | Unset
        )
        if isinstance(_contract_type, Unset):
            contract_type = UNSET
        else:
            contract_type = CreateChangeEventResponse201ChangeItemsItemCostImpactContractConfirmedType0ContractType(
                _contract_type
            )

        id = d.pop("id", UNSET)

        def _parse_number(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        number = _parse_number(d.pop("number", UNSET))

        status = d.pop("status", UNSET)

        def _parse_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title = _parse_title(d.pop("title", UNSET))

        create_change_event_response_201_change_items_item_cost_impact_contract_confirmed_type_0 = cls(
            contract_type=contract_type,
            id=id,
            number=number,
            status=status,
            title=title,
        )

        create_change_event_response_201_change_items_item_cost_impact_contract_confirmed_type_0.additional_properties = d
        return create_change_event_response_201_change_items_item_cost_impact_contract_confirmed_type_0

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
