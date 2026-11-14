from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_rfi_response_201_schedule_impact_type_0_status import (
    CreateRfiResponse201ScheduleImpactType0Status,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateRfiResponse201ScheduleImpactType0")


@_attrs_define
class CreateRfiResponse201ScheduleImpactType0:
    """
    Attributes:
        status (CreateRfiResponse201ScheduleImpactType0Status | Unset): Schedule impact status
        value (int | None | Unset): Schedule impact value in days
    """

    status: CreateRfiResponse201ScheduleImpactType0Status | Unset = UNSET
    value: int | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        value: int | None | Unset
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
        status: CreateRfiResponse201ScheduleImpactType0Status | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = CreateRfiResponse201ScheduleImpactType0Status(_status)

        def _parse_value(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        value = _parse_value(d.pop("value", UNSET))

        create_rfi_response_201_schedule_impact_type_0 = cls(
            status=status,
            value=value,
        )

        create_rfi_response_201_schedule_impact_type_0.additional_properties = d
        return create_rfi_response_201_schedule_impact_type_0

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
