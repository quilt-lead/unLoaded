from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

if TYPE_CHECKING:
    from ..models.issue_payload_custom_attributes_item_value import (
        IssuePayloadCustomAttributesItemValue,
    )


T = TypeVar("T", bound="IssuePayloadCustomAttributesItem")


@_attrs_define
class IssuePayloadCustomAttributesItem:
    """
    Attributes:
        attribute_definition_id (str): The unique identifier of the custom attribute.
        value (IssuePayloadCustomAttributesItemValue): Custom attribute value. Possible value types: string, number,
            null.
    """

    attribute_definition_id: str
    value: IssuePayloadCustomAttributesItemValue
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attribute_definition_id = self.attribute_definition_id

        value = self.value.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "attributeDefinitionId": attribute_definition_id,
                "value": value,
            }
        )

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_payload_custom_attributes_item_value import (
            IssuePayloadCustomAttributesItemValue,
        )

        d = dict(src_dict)
        attribute_definition_id = d.pop("attributeDefinitionId")

        value = IssuePayloadCustomAttributesItemValue.from_dict(d.pop("value"))

        issue_payload_custom_attributes_item = cls(
            attribute_definition_id=attribute_definition_id,
            value=value,
        )

        issue_payload_custom_attributes_item.additional_properties = d
        return issue_payload_custom_attributes_item

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
