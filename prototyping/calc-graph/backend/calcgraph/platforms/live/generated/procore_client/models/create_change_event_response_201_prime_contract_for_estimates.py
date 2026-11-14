from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateChangeEventResponse201PrimeContractForEstimates")


@_attrs_define
class CreateChangeEventResponse201PrimeContractForEstimates:
    """
    Attributes:
        id (int | Unset): ID
        name (str | Unset): name of contract
        number (str | Unset): contract number
    """

    id: int | Unset = UNSET
    name: str | Unset = UNSET
    number: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        id = self.id

        name = self.name

        number = self.number

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if number is not UNSET:
            field_dict["number"] = number

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        number = d.pop("number", UNSET)

        create_change_event_response_201_prime_contract_for_estimates = cls(
            id=id,
            name=name,
            number=number,
        )

        create_change_event_response_201_prime_contract_for_estimates.additional_properties = d
        return create_change_event_response_201_prime_contract_for_estimates

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
