from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_submittals_response_200_item_ball_in_court_item_vendor_type_0 import (
        ListSubmittalsResponse200ItemBallInCourtItemVendorType0,
    )


T = TypeVar("T", bound="ListSubmittalsResponse200ItemBallInCourtItem")


@_attrs_define
class ListSubmittalsResponse200ItemBallInCourtItem:
    """
    Attributes:
        id (int | Unset): ID
        initials (str | Unset):
        name (str | Unset): Name
        vendor (ListSubmittalsResponse200ItemBallInCourtItemVendorType0 | None | Unset):
    """

    id: int | Unset = UNSET
    initials: str | Unset = UNSET
    name: str | Unset = UNSET
    vendor: ListSubmittalsResponse200ItemBallInCourtItemVendorType0 | None | Unset = (
        UNSET
    )
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.list_submittals_response_200_item_ball_in_court_item_vendor_type_0 import (
            ListSubmittalsResponse200ItemBallInCourtItemVendorType0,
        )

        id = self.id

        initials = self.initials

        name = self.name

        vendor: dict[str, Any] | None | Unset
        if isinstance(self.vendor, Unset):
            vendor = UNSET
        elif isinstance(
            self.vendor, ListSubmittalsResponse200ItemBallInCourtItemVendorType0
        ):
            vendor = self.vendor.to_dict()
        else:
            vendor = self.vendor

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if id is not UNSET:
            field_dict["id"] = id
        if initials is not UNSET:
            field_dict["initials"] = initials
        if name is not UNSET:
            field_dict["name"] = name
        if vendor is not UNSET:
            field_dict["vendor"] = vendor

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_submittals_response_200_item_ball_in_court_item_vendor_type_0 import (
            ListSubmittalsResponse200ItemBallInCourtItemVendorType0,
        )

        d = dict(src_dict)
        id = d.pop("id", UNSET)

        initials = d.pop("initials", UNSET)

        name = d.pop("name", UNSET)

        def _parse_vendor(
            data: object,
        ) -> ListSubmittalsResponse200ItemBallInCourtItemVendorType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                vendor_type_0 = (
                    ListSubmittalsResponse200ItemBallInCourtItemVendorType0.from_dict(
                        data
                    )
                )

                return vendor_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemBallInCourtItemVendorType0 | None | Unset,
                data,
            )

        vendor = _parse_vendor(d.pop("vendor", UNSET))

        list_submittals_response_200_item_ball_in_court_item = cls(
            id=id,
            initials=initials,
            name=name,
            vendor=vendor,
        )

        list_submittals_response_200_item_ball_in_court_item.additional_properties = d
        return list_submittals_response_200_item_ball_in_court_item

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
