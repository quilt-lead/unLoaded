from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_rfi_body_rfi_schedule_impact_status import (
    CreateRfiBodyRfiScheduleImpactStatus,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateRfiBodyRfiScheduleImpact")


@_attrs_define
class CreateRfiBodyRfiScheduleImpact:
    """The Schedule Impact of the RFI

    Attributes:
        status (CreateRfiBodyRfiScheduleImpactStatus | Unset): The Status of the Schedule Impact
        value (int | Unset): The Value in days of the Schedule Impact
    """

    status: CreateRfiBodyRfiScheduleImpactStatus | Unset = UNSET
    value: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

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
        status: CreateRfiBodyRfiScheduleImpactStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = CreateRfiBodyRfiScheduleImpactStatus(_status)

        value = d.pop("value", UNSET)

        create_rfi_body_rfi_schedule_impact = cls(
            status=status,
            value=value,
        )

        create_rfi_body_rfi_schedule_impact.additional_properties = d
        return create_rfi_body_rfi_schedule_impact

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
