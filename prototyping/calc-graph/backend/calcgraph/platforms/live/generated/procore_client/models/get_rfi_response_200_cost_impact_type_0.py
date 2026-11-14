from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.get_rfi_response_200_cost_impact_type_0_status import (
    GetRfiResponse200CostImpactType0Status,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="GetRfiResponse200CostImpactType0")


@_attrs_define
class GetRfiResponse200CostImpactType0:
    """
    Attributes:
        status (GetRfiResponse200CostImpactType0Status | Unset): Cost impact status
        value (None | str | Unset): Cost impact value in dollars
    """

    status: GetRfiResponse200CostImpactType0Status | Unset = UNSET
    value: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        value: None | str | Unset
        if isinstance(self.value, Unset):
            value = UNSET
        else:
            value = self.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if status is not UNSET:
            field_dict["status"] = status
        if value is not UNSET:
            field_dict["value"] = value

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _status = d.pop("status", UNSET)
        status: GetRfiResponse200CostImpactType0Status | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = GetRfiResponse200CostImpactType0Status(_status)

        def _parse_value(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        value = _parse_value(d.pop("value", UNSET))

        get_rfi_response_200_cost_impact_type_0 = cls(
            status=status,
            value=value,
        )

        get_rfi_response_200_cost_impact_type_0.additional_properties = d
        return get_rfi_response_200_cost_impact_type_0

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
