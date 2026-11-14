from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_change_order_packages_response_200_item_status import (
    ListChangeOrderPackagesResponse200ItemStatus,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_change_order_packages_response_200_item_contract import (
        ListChangeOrderPackagesResponse200ItemContract,
    )
    from ..models.list_change_order_packages_response_200_item_currency_configuration import (
        ListChangeOrderPackagesResponse200ItemCurrencyConfiguration,
    )
    from ..models.list_change_order_packages_response_200_item_custom_fields import (
        ListChangeOrderPackagesResponse200ItemCustomFields,
    )
    from ..models.list_change_order_packages_response_200_item_designated_reviewer import (
        ListChangeOrderPackagesResponse200ItemDesignatedReviewer,
    )


T = TypeVar("T", bound="ListChangeOrderPackagesResponse200Item")


@_attrs_define
class ListChangeOrderPackagesResponse200Item:
    """
    Attributes:
        contract (ListChangeOrderPackagesResponse200ItemContract | Unset): Contract details including the associated
            vendor
        contract_id (int | Unset): ID of the parent contract this change order package belongs to.
        created_at (datetime.datetime | Unset): Timestamp when the change order package was created, in ISO 8601 format.
        created_by_id (int | Unset): ID of the user who created this change order package.
        currency_configuration (ListChangeOrderPackagesResponse200ItemCurrencyConfiguration | Unset):
        custom_fields (ListChangeOrderPackagesResponse200ItemCustomFields | Unset):
        deleted_at (datetime.datetime | Unset): Timestamp when the change order package was deleted, in ISO 8601 format.
            Null unless the record has been deleted.
        designated_reviewer (ListChangeOrderPackagesResponse200ItemDesignatedReviewer | Unset): User designated to
            review this change order package.
        due_date (datetime.date | Unset): Date the change order package is due (YYYY-MM-DD).
        executed (bool | Unset): When true, the change order package has been fully executed (signed by all parties).
        grand_total (str | Unset): Total amount of the change order package including markup. Computed from its line
            items.
        id (int | Unset): Unique identifier for this change order package. Use as the {id} path parameter to retrieve or
            update it.
        invoiced_date (datetime.date | Unset): Date the change order package was invoiced (YYYY-MM-DD).
        number (str | Unset): Auto-generated, human-readable number identifying the change order package within its
            contract.
        origin_code (str | Unset): Code identifying this record in an external or integrated system.
        origin_data (str | Unset): Free-form data payload from the external system that created this record.
        origin_id (str | Unset): Identifier of this record in an external or integrated system.
        paid_date (datetime.date | Unset): Date the change order package was paid (YYYY-MM-DD).
        reviewed_at (datetime.datetime | Unset): Timestamp when the change order package was reviewed, in ISO 8601
            format.
        revision (int | Unset): Revision number for this change order package. This is a manual input field; it is not
            automatically incremented.
        signed_change_order_received_date (datetime.date | Unset): Date the signed change order was received from the
            vendor (YYYY-MM-DD).
        status (ListChangeOrderPackagesResponse200ItemStatus | Unset): Status of the change order package. Note:
            pending_billable is only available in 1-tier change order projects.
        title (str | Unset): Short title summarizing the change order package.
        updated_at (datetime.datetime | Unset): Timestamp when the change order package was last updated, in ISO 8601
            format.
    """

    contract: ListChangeOrderPackagesResponse200ItemContract | Unset = UNSET
    contract_id: int | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by_id: int | Unset = UNSET
    currency_configuration: (
        ListChangeOrderPackagesResponse200ItemCurrencyConfiguration | Unset
    ) = UNSET
    custom_fields: ListChangeOrderPackagesResponse200ItemCustomFields | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    designated_reviewer: (
        ListChangeOrderPackagesResponse200ItemDesignatedReviewer | Unset
    ) = UNSET
    due_date: datetime.date | Unset = UNSET
    executed: bool | Unset = UNSET
    grand_total: str | Unset = UNSET
    id: int | Unset = UNSET
    invoiced_date: datetime.date | Unset = UNSET
    number: str | Unset = UNSET
    origin_code: str | Unset = UNSET
    origin_data: str | Unset = UNSET
    origin_id: str | Unset = UNSET
    paid_date: datetime.date | Unset = UNSET
    reviewed_at: datetime.datetime | Unset = UNSET
    revision: int | Unset = UNSET
    signed_change_order_received_date: datetime.date | Unset = UNSET
    status: ListChangeOrderPackagesResponse200ItemStatus | Unset = UNSET
    title: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        contract: dict[str, Any] | Unset = UNSET
        if not isinstance(self.contract, Unset):
            contract = self.contract.to_dict()

        contract_id = self.contract_id

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        created_by_id = self.created_by_id

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        custom_fields: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_fields, Unset):
            custom_fields = self.custom_fields.to_dict()

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        designated_reviewer: dict[str, Any] | Unset = UNSET
        if not isinstance(self.designated_reviewer, Unset):
            designated_reviewer = self.designated_reviewer.to_dict()

        due_date: str | Unset = UNSET
        if not isinstance(self.due_date, Unset):
            due_date = self.due_date.isoformat()

        executed = self.executed

        grand_total = self.grand_total

        id = self.id

        invoiced_date: str | Unset = UNSET
        if not isinstance(self.invoiced_date, Unset):
            invoiced_date = self.invoiced_date.isoformat()

        number = self.number

        origin_code = self.origin_code

        origin_data = self.origin_data

        origin_id = self.origin_id

        paid_date: str | Unset = UNSET
        if not isinstance(self.paid_date, Unset):
            paid_date = self.paid_date.isoformat()

        reviewed_at: str | Unset = UNSET
        if not isinstance(self.reviewed_at, Unset):
            reviewed_at = self.reviewed_at.isoformat()

        revision = self.revision

        signed_change_order_received_date: str | Unset = UNSET
        if not isinstance(self.signed_change_order_received_date, Unset):
            signed_change_order_received_date = (
                self.signed_change_order_received_date.isoformat()
            )

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        title = self.title

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if contract is not UNSET:
            field_dict["contract"] = contract
        if contract_id is not UNSET:
            field_dict["contract_id"] = contract_id
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by_id is not UNSET:
            field_dict["created_by_id"] = created_by_id
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if designated_reviewer is not UNSET:
            field_dict["designated_reviewer"] = designated_reviewer
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if executed is not UNSET:
            field_dict["executed"] = executed
        if grand_total is not UNSET:
            field_dict["grand_total"] = grand_total
        if id is not UNSET:
            field_dict["id"] = id
        if invoiced_date is not UNSET:
            field_dict["invoiced_date"] = invoiced_date
        if number is not UNSET:
            field_dict["number"] = number
        if origin_code is not UNSET:
            field_dict["origin_code"] = origin_code
        if origin_data is not UNSET:
            field_dict["origin_data"] = origin_data
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id
        if paid_date is not UNSET:
            field_dict["paid_date"] = paid_date
        if reviewed_at is not UNSET:
            field_dict["reviewed_at"] = reviewed_at
        if revision is not UNSET:
            field_dict["revision"] = revision
        if signed_change_order_received_date is not UNSET:
            field_dict["signed_change_order_received_date"] = (
                signed_change_order_received_date
            )
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_change_order_packages_response_200_item_contract import (
            ListChangeOrderPackagesResponse200ItemContract,
        )
        from ..models.list_change_order_packages_response_200_item_currency_configuration import (
            ListChangeOrderPackagesResponse200ItemCurrencyConfiguration,
        )
        from ..models.list_change_order_packages_response_200_item_custom_fields import (
            ListChangeOrderPackagesResponse200ItemCustomFields,
        )
        from ..models.list_change_order_packages_response_200_item_designated_reviewer import (
            ListChangeOrderPackagesResponse200ItemDesignatedReviewer,
        )

        d = dict(src_dict)
        _contract = d.pop("contract", UNSET)
        contract: ListChangeOrderPackagesResponse200ItemContract | Unset
        if isinstance(_contract, Unset):
            contract = UNSET
        else:
            contract = ListChangeOrderPackagesResponse200ItemContract.from_dict(
                _contract
            )

        contract_id = d.pop("contract_id", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        created_by_id = d.pop("created_by_id", UNSET)

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: (
            ListChangeOrderPackagesResponse200ItemCurrencyConfiguration | Unset
        )
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = (
                ListChangeOrderPackagesResponse200ItemCurrencyConfiguration.from_dict(
                    _currency_configuration
                )
            )

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: ListChangeOrderPackagesResponse200ItemCustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = (
                ListChangeOrderPackagesResponse200ItemCustomFields.from_dict(
                    _custom_fields
                )
            )

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        _designated_reviewer = d.pop("designated_reviewer", UNSET)
        designated_reviewer: (
            ListChangeOrderPackagesResponse200ItemDesignatedReviewer | Unset
        )
        if isinstance(_designated_reviewer, Unset):
            designated_reviewer = UNSET
        else:
            designated_reviewer = (
                ListChangeOrderPackagesResponse200ItemDesignatedReviewer.from_dict(
                    _designated_reviewer
                )
            )

        _due_date = d.pop("due_date", UNSET)
        due_date: datetime.date | Unset
        if isinstance(_due_date, Unset):
            due_date = UNSET
        else:
            due_date = datetime.date.fromisoformat(_due_date)

        executed = d.pop("executed", UNSET)

        grand_total = d.pop("grand_total", UNSET)

        id = d.pop("id", UNSET)

        _invoiced_date = d.pop("invoiced_date", UNSET)
        invoiced_date: datetime.date | Unset
        if isinstance(_invoiced_date, Unset):
            invoiced_date = UNSET
        else:
            invoiced_date = datetime.date.fromisoformat(_invoiced_date)

        number = d.pop("number", UNSET)

        origin_code = d.pop("origin_code", UNSET)

        origin_data = d.pop("origin_data", UNSET)

        origin_id = d.pop("origin_id", UNSET)

        _paid_date = d.pop("paid_date", UNSET)
        paid_date: datetime.date | Unset
        if isinstance(_paid_date, Unset):
            paid_date = UNSET
        else:
            paid_date = datetime.date.fromisoformat(_paid_date)

        _reviewed_at = d.pop("reviewed_at", UNSET)
        reviewed_at: datetime.datetime | Unset
        if isinstance(_reviewed_at, Unset):
            reviewed_at = UNSET
        else:
            reviewed_at = datetime.datetime.fromisoformat(_reviewed_at)

        revision = d.pop("revision", UNSET)

        _signed_change_order_received_date = d.pop(
            "signed_change_order_received_date", UNSET
        )
        signed_change_order_received_date: datetime.date | Unset
        if isinstance(_signed_change_order_received_date, Unset):
            signed_change_order_received_date = UNSET
        else:
            signed_change_order_received_date = datetime.date.fromisoformat(
                _signed_change_order_received_date
            )

        _status = d.pop("status", UNSET)
        status: ListChangeOrderPackagesResponse200ItemStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ListChangeOrderPackagesResponse200ItemStatus(_status)

        title = d.pop("title", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_change_order_packages_response_200_item = cls(
            contract=contract,
            contract_id=contract_id,
            created_at=created_at,
            created_by_id=created_by_id,
            currency_configuration=currency_configuration,
            custom_fields=custom_fields,
            deleted_at=deleted_at,
            designated_reviewer=designated_reviewer,
            due_date=due_date,
            executed=executed,
            grand_total=grand_total,
            id=id,
            invoiced_date=invoiced_date,
            number=number,
            origin_code=origin_code,
            origin_data=origin_data,
            origin_id=origin_id,
            paid_date=paid_date,
            reviewed_at=reviewed_at,
            revision=revision,
            signed_change_order_received_date=signed_change_order_received_date,
            status=status,
            title=title,
            updated_at=updated_at,
        )

        list_change_order_packages_response_200_item.additional_properties = d
        return list_change_order_packages_response_200_item

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
