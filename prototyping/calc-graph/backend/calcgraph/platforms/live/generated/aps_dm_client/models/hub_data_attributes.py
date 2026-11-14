from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.region import Region
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.base_attributes_extension_object_with_schema_link import (
        BaseAttributesExtensionObjectWithSchemaLink,
    )


T = TypeVar("T", bound="HubDataAttributes")


@_attrs_define
class HubDataAttributes:
    """The properties of the hub.

    Attributes:
        extension (BaseAttributesExtensionObjectWithSchemaLink | Unset): A container of additional properties that
            extends this resource.
        name (str | Unset): A human friendly name to identify the hub.
        region (Region | Unset): Specifies where the hub is stored. Possible values are:

            - ``US`` - Data center for the US region.
            - ``EMEA`` - Data center for the European Union, Middle East, and Africa regions.
            - ``AUS`` - Data center for the Australia region.
            - ``CAN`` - Data center for the Canada region.
            - ``DEU`` - Data center for the Germany region.
            - ``IND`` - Data center for the India region.
            - ``JPN`` - Data center for the Japan region.
            - ``GBR`` - Data center for the United Kingdom region.
    """

    extension: BaseAttributesExtensionObjectWithSchemaLink | Unset = UNSET
    name: str | Unset = UNSET
    region: Region | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        extension: dict[str, Any] | Unset = UNSET
        if not isinstance(self.extension, Unset):
            extension = self.extension.to_dict()

        name = self.name

        region: str | Unset = UNSET
        if not isinstance(self.region, Unset):
            region = self.region.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if extension is not UNSET:
            field_dict["extension"] = extension
        if name is not UNSET:
            field_dict["name"] = name
        if region is not UNSET:
            field_dict["region"] = region

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.base_attributes_extension_object_with_schema_link import (
            BaseAttributesExtensionObjectWithSchemaLink,
        )

        d = dict(src_dict)
        _extension = d.pop("extension", UNSET)
        extension: BaseAttributesExtensionObjectWithSchemaLink | Unset
        if isinstance(_extension, Unset):
            extension = UNSET
        else:
            extension = BaseAttributesExtensionObjectWithSchemaLink.from_dict(
                _extension
            )

        name = d.pop("name", UNSET)

        _region = d.pop("region", UNSET)
        region: Region | Unset
        if isinstance(_region, Unset):
            region = UNSET
        else:
            region = Region(_region)

        hub_data_attributes = cls(
            extension=extension,
            name=name,
            region=region,
        )

        hub_data_attributes.additional_properties = d
        return hub_data_attributes

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
