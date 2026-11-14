from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_commitments_response_200_item_status import (
    ListCommitmentsResponse200ItemStatus,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_commitments_response_200_item_vendor import (
        ListCommitmentsResponse200ItemVendor,
    )


T = TypeVar("T", bound="ListCommitmentsResponse200Item")


@_attrs_define
class ListCommitmentsResponse200Item:
    """
    Attributes:
        created_at (datetime.datetime | Unset): Created at
        delivery_date (datetime.date | Unset): Delivery date
        description (str | Unset): Description of the commitment contract.
        executed (bool | Unset): Executed status
        id (float | Unset): Commitment ID
        number (str | Unset): User-assigned contract number identifying the commitment.
        private (bool | Unset): If true, visible to admins only; otherwise visible to those with access to the parent
            contract.
        status (ListCommitmentsResponse200ItemStatus | Unset): Current status of the commitment contract.
        title (str | Unset): Title of the commitment contract.
        vendor (ListCommitmentsResponse200ItemVendor | Unset):
    """

    created_at: datetime.datetime | Unset = UNSET
    delivery_date: datetime.date | Unset = UNSET
    description: str | Unset = UNSET
    executed: bool | Unset = UNSET
    id: float | Unset = UNSET
    number: str | Unset = UNSET
    private: bool | Unset = UNSET
    status: ListCommitmentsResponse200ItemStatus | Unset = UNSET
    title: str | Unset = UNSET
    vendor: ListCommitmentsResponse200ItemVendor | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        delivery_date: str | Unset = UNSET
        if not isinstance(self.delivery_date, Unset):
            delivery_date = self.delivery_date.isoformat()

        description = self.description

        executed = self.executed

        id = self.id

        number = self.number

        private = self.private

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        title = self.title

        vendor: dict[str, Any] | Unset = UNSET
        if not isinstance(self.vendor, Unset):
            vendor = self.vendor.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if delivery_date is not UNSET:
            field_dict["delivery_date"] = delivery_date
        if description is not UNSET:
            field_dict["description"] = description
        if executed is not UNSET:
            field_dict["executed"] = executed
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number
        if private is not UNSET:
            field_dict["private"] = private
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if vendor is not UNSET:
            field_dict["vendor"] = vendor

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_commitments_response_200_item_vendor import (
            ListCommitmentsResponse200ItemVendor,
        )

        d = dict(src_dict)
        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _delivery_date = d.pop("delivery_date", UNSET)
        delivery_date: datetime.date | Unset
        if isinstance(_delivery_date, Unset):
            delivery_date = UNSET
        else:
            delivery_date = datetime.date.fromisoformat(_delivery_date)

        description = d.pop("description", UNSET)

        executed = d.pop("executed", UNSET)

        id = d.pop("id", UNSET)

        number = d.pop("number", UNSET)

        private = d.pop("private", UNSET)

        _status = d.pop("status", UNSET)
        status: ListCommitmentsResponse200ItemStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ListCommitmentsResponse200ItemStatus(_status)

        title = d.pop("title", UNSET)

        _vendor = d.pop("vendor", UNSET)
        vendor: ListCommitmentsResponse200ItemVendor | Unset
        if isinstance(_vendor, Unset):
            vendor = UNSET
        else:
            vendor = ListCommitmentsResponse200ItemVendor.from_dict(_vendor)

        list_commitments_response_200_item = cls(
            created_at=created_at,
            delivery_date=delivery_date,
            description=description,
            executed=executed,
            id=id,
            number=number,
            private=private,
            status=status,
            title=title,
            vendor=vendor,
        )

        list_commitments_response_200_item.additional_properties = d
        return list_commitments_response_200_item

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
