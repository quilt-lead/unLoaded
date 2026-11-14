from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar(
    "T", bound="CreateChangeEventResponse201ChangeItemsItemCurrencyConfiguration"
)


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemCurrencyConfiguration:
    """Currency configuration information

    Attributes:
        currency_iso_code (None | str | Unset): currency ISO code
    """

    currency_iso_code: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        currency_iso_code: None | str | Unset
        if isinstance(self.currency_iso_code, Unset):
            currency_iso_code = UNSET
        else:
            currency_iso_code = self.currency_iso_code

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if currency_iso_code is not UNSET:
            field_dict["currency_iso_code"] = currency_iso_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)

        def _parse_currency_iso_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        currency_iso_code = _parse_currency_iso_code(d.pop("currency_iso_code", UNSET))

        create_change_event_response_201_change_items_item_currency_configuration = cls(
            currency_iso_code=currency_iso_code,
        )

        create_change_event_response_201_change_items_item_currency_configuration.additional_properties = d
        return create_change_event_response_201_change_items_item_currency_configuration

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
