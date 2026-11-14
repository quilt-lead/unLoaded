from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_rfis_response_200_item_questions_item_errors_item import (
        ListRfisResponse200ItemQuestionsItemErrorsItem,
    )


T = TypeVar("T", bound="ListRfisResponse200ItemQuestionsItem")


@_attrs_define
class ListRfisResponse200ItemQuestionsItem:
    """
    Attributes:
        body (str | Unset): Body
        errors (list[ListRfisResponse200ItemQuestionsItemErrorsItem] | Unset): Errors
        id (int | Unset): ID
    """

    body: str | Unset = UNSET
    errors: list[ListRfisResponse200ItemQuestionsItemErrorsItem] | Unset = UNSET
    id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = self.body

        errors: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.errors, Unset):
            errors = []
            for errors_item_data in self.errors:
                errors_item = errors_item_data.to_dict()
                errors.append(errors_item)

        id = self.id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if body is not UNSET:
            field_dict["body"] = body
        if errors is not UNSET:
            field_dict["errors"] = errors
        if id is not UNSET:
            field_dict["id"] = id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_rfis_response_200_item_questions_item_errors_item import (
            ListRfisResponse200ItemQuestionsItemErrorsItem,
        )

        d = dict(src_dict)
        body = d.pop("body", UNSET)

        _errors = d.pop("errors", UNSET)
        errors: list[ListRfisResponse200ItemQuestionsItemErrorsItem] | Unset = UNSET
        if _errors is not UNSET:
            errors = []
            for errors_item_data in _errors:
                errors_item = ListRfisResponse200ItemQuestionsItemErrorsItem.from_dict(
                    errors_item_data
                )

                errors.append(errors_item)

        id = d.pop("id", UNSET)

        list_rfis_response_200_item_questions_item = cls(
            body=body,
            errors=errors,
            id=id,
        )

        list_rfis_response_200_item_questions_item.additional_properties = d
        return list_rfis_response_200_item_questions_item

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
