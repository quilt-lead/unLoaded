from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issue_custom_attributes_item_value import (
        IssueCustomAttributesItemValue,
    )


T = TypeVar("T", bound="IssueCustomAttributesItem")


@_attrs_define
class IssueCustomAttributesItem:
    """
    Attributes:
        attribute_definition_id (str | Unset): The unique identifier of the custom attribute.
        title (str | Unset): Free text description of the attribute.
        type_ (str | Unset): The type of attribute. Possible values: numeric, paragraph, list (this corresponds to
            dropdown in the UI), text.
        value (IssueCustomAttributesItemValue | Unset): Custom attribute value. Possible value types: string, number,
            null.
    """

    attribute_definition_id: str | Unset = UNSET
    title: str | Unset = UNSET
    type_: str | Unset = UNSET
    value: IssueCustomAttributesItemValue | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attribute_definition_id = self.attribute_definition_id

        title = self.title

        type_ = self.type_

        value: dict[str, Any] | Unset = UNSET
        if not isinstance(self.value, Unset):
            value = self.value.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if attribute_definition_id is not UNSET:
            field_dict["attributeDefinitionId"] = attribute_definition_id
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_
        if value is not UNSET:
            field_dict["value"] = value

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_custom_attributes_item_value import (
            IssueCustomAttributesItemValue,
        )

        d = dict(src_dict)
        attribute_definition_id = d.pop("attributeDefinitionId", UNSET)

        title = d.pop("title", UNSET)

        type_ = d.pop("type", UNSET)

        _value = d.pop("value", UNSET)
        value: IssueCustomAttributesItemValue | Unset
        if isinstance(_value, Unset):
            value = UNSET
        else:
            value = IssueCustomAttributesItemValue.from_dict(_value)

        issue_custom_attributes_item = cls(
            attribute_definition_id=attribute_definition_id,
            title=title,
            type_=type_,
            value=value,
        )

        issue_custom_attributes_item.additional_properties = d
        return issue_custom_attributes_item

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
