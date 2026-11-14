from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_submittal_body_submittal import CreateSubmittalBodySubmittal


T = TypeVar("T", bound="CreateSubmittalBody")


@_attrs_define
class CreateSubmittalBody:
    """
    Attributes:
        submittal (CreateSubmittalBodySubmittal | Unset):
    """

    submittal: CreateSubmittalBodySubmittal | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        submittal: dict[str, Any] | Unset = UNSET
        if not isinstance(self.submittal, Unset):
            submittal = self.submittal.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if submittal is not UNSET:
            field_dict["submittal"] = submittal

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_submittal_body_submittal import (
            CreateSubmittalBodySubmittal,
        )

        d = dict(src_dict)
        _submittal = d.pop("submittal", UNSET)
        submittal: CreateSubmittalBodySubmittal | Unset
        if isinstance(_submittal, Unset):
            submittal = UNSET
        else:
            submittal = CreateSubmittalBodySubmittal.from_dict(_submittal)

        create_submittal_body = cls(
            submittal=submittal,
        )

        create_submittal_body.additional_properties = d
        return create_submittal_body

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
