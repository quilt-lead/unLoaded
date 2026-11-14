from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.procore_change_order_package_status import ProcoreChangeOrderPackageStatus
from ..models.procore_change_order_package_type import ProcoreChangeOrderPackageType
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_order_package_attachments_item import (
        ProcoreChangeOrderPackageAttachmentsItem,
    )
    from ..models.procore_change_order_package_creator import (
        ProcoreChangeOrderPackageCreator,
    )
    from ..models.procore_change_order_package_currency_configuration import (
        ProcoreChangeOrderPackageCurrencyConfiguration,
    )
    from ..models.procore_change_order_package_custom_fields import (
        ProcoreChangeOrderPackageCustomFields,
    )
    from ..models.procore_change_order_package_designated_reviewer import (
        ProcoreChangeOrderPackageDesignatedReviewer,
    )
    from ..models.procore_change_order_package_line_items_item import (
        ProcoreChangeOrderPackageLineItemsItem,
    )
    from ..models.procore_change_order_package_reviewer import (
        ProcoreChangeOrderPackageReviewer,
    )


T = TypeVar("T", bound="ProcoreChangeOrderPackage")


@_attrs_define
class ProcoreChangeOrderPackage:
    """
    Attributes:
        attachments (list[ProcoreChangeOrderPackageAttachmentsItem] | Unset):
        contract_id (int | Unset): ID of the parent contract this change order package belongs to.
        created_at (datetime.datetime | Unset): Timestamp when the change order package was created, in ISO 8601 format.
        creator (ProcoreChangeOrderPackageCreator | Unset):
        currency_configuration (ProcoreChangeOrderPackageCurrencyConfiguration | Unset):
        custom_fields (ProcoreChangeOrderPackageCustomFields | Unset):
        deleted_at (datetime.datetime | Unset): Timestamp when the change order package was deleted, in ISO 8601 format.
            Null unless the record has been deleted.
        description (str | Unset): Detailed description of the scope or reason for the change order package.
        designated_reviewer (ProcoreChangeOrderPackageDesignatedReviewer | Unset):
        due_date (datetime.date | Unset): Date the change order package is due (YYYY-MM-DD).
        executed (bool | Unset): When true, the change order package has been fully executed (signed by all parties).
        grand_total (str | Unset): Total amount of the change order package including markup. Computed from its line
            items.
        id (int | Unset): Unique identifier for this change order package. Use as the {id} path parameter to retrieve or
            update it.
        invoiced_date (datetime.date | Unset): Date the change order package was invoiced (YYYY-MM-DD).
        line_items (list[ProcoreChangeOrderPackageLineItemsItem] | Unset):
        number (str | Unset): Auto-generated, human-readable number identifying the change order package within its
            contract.
        origin_code (str | Unset): Code identifying this record in an external or integrated system.
        origin_data (str | Unset): Free-form data payload from the external system that created this record.
        origin_id (str | Unset): Identifier of this record in an external or integrated system.
        paid_date (datetime.date | Unset): Date the change order package was paid (YYYY-MM-DD).
        position (int | Unset): Sort position of the change order package relative to others in its contract.
        private (bool | Unset): If true, visible to admins only; otherwise visible to those with access to the parent
            contract.
        review_notes (str | Unset): Notes to assist the reviewer
        reviewed_at (datetime.datetime | Unset): Timestamp when the change order package was reviewed, in ISO 8601
            format.
        reviewer (ProcoreChangeOrderPackageReviewer | Unset):
        revised_substantial_completion_date (datetime.date | Unset): Revised project substantial-completion date
            resulting from this change order package (YYYY-MM-DD).
        revision (int | Unset): Revision number, incremented each time the change order package is revised.
        schedule_impact_amount (int | Unset): Estimated impact to the project schedule, in days.
        signed_change_order_received_date (datetime.date | Unset): Date the signed change order was received from the
            vendor (YYYY-MM-DD).
        status (ProcoreChangeOrderPackageStatus | Unset): Workflow status of the change order package.
        title (str | Unset): Short title summarizing the change order package.
        type_ (ProcoreChangeOrderPackageType | Unset): Subtype of the change order package indicating which kind of
            contract it belongs to.
        updated_at (datetime.datetime | Unset): Timestamp when the change order package was last updated, in ISO 8601
            format.
    """

    attachments: list[ProcoreChangeOrderPackageAttachmentsItem] | Unset = UNSET
    contract_id: int | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    creator: ProcoreChangeOrderPackageCreator | Unset = UNSET
    currency_configuration: ProcoreChangeOrderPackageCurrencyConfiguration | Unset = (
        UNSET
    )
    custom_fields: ProcoreChangeOrderPackageCustomFields | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    description: str | Unset = UNSET
    designated_reviewer: ProcoreChangeOrderPackageDesignatedReviewer | Unset = UNSET
    due_date: datetime.date | Unset = UNSET
    executed: bool | Unset = UNSET
    grand_total: str | Unset = UNSET
    id: int | Unset = UNSET
    invoiced_date: datetime.date | Unset = UNSET
    line_items: list[ProcoreChangeOrderPackageLineItemsItem] | Unset = UNSET
    number: str | Unset = UNSET
    origin_code: str | Unset = UNSET
    origin_data: str | Unset = UNSET
    origin_id: str | Unset = UNSET
    paid_date: datetime.date | Unset = UNSET
    position: int | Unset = UNSET
    private: bool | Unset = UNSET
    review_notes: str | Unset = UNSET
    reviewed_at: datetime.datetime | Unset = UNSET
    reviewer: ProcoreChangeOrderPackageReviewer | Unset = UNSET
    revised_substantial_completion_date: datetime.date | Unset = UNSET
    revision: int | Unset = UNSET
    schedule_impact_amount: int | Unset = UNSET
    signed_change_order_received_date: datetime.date | Unset = UNSET
    status: ProcoreChangeOrderPackageStatus | Unset = UNSET
    title: str | Unset = UNSET
    type_: ProcoreChangeOrderPackageType | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        contract_id = self.contract_id

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        creator: dict[str, Any] | Unset = UNSET
        if not isinstance(self.creator, Unset):
            creator = self.creator.to_dict()

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        custom_fields: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_fields, Unset):
            custom_fields = self.custom_fields.to_dict()

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        description = self.description

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

        line_items: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.line_items, Unset):
            line_items = []
            for line_items_item_data in self.line_items:
                line_items_item = line_items_item_data.to_dict()
                line_items.append(line_items_item)

        number = self.number

        origin_code = self.origin_code

        origin_data = self.origin_data

        origin_id = self.origin_id

        paid_date: str | Unset = UNSET
        if not isinstance(self.paid_date, Unset):
            paid_date = self.paid_date.isoformat()

        position = self.position

        private = self.private

        review_notes = self.review_notes

        reviewed_at: str | Unset = UNSET
        if not isinstance(self.reviewed_at, Unset):
            reviewed_at = self.reviewed_at.isoformat()

        reviewer: dict[str, Any] | Unset = UNSET
        if not isinstance(self.reviewer, Unset):
            reviewer = self.reviewer.to_dict()

        revised_substantial_completion_date: str | Unset = UNSET
        if not isinstance(self.revised_substantial_completion_date, Unset):
            revised_substantial_completion_date = (
                self.revised_substantial_completion_date.isoformat()
            )

        revision = self.revision

        schedule_impact_amount = self.schedule_impact_amount

        signed_change_order_received_date: str | Unset = UNSET
        if not isinstance(self.signed_change_order_received_date, Unset):
            signed_change_order_received_date = (
                self.signed_change_order_received_date.isoformat()
            )

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        title = self.title

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if contract_id is not UNSET:
            field_dict["contract_id"] = contract_id
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if creator is not UNSET:
            field_dict["creator"] = creator
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if description is not UNSET:
            field_dict["description"] = description
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
        if line_items is not UNSET:
            field_dict["line_items"] = line_items
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
        if position is not UNSET:
            field_dict["position"] = position
        if private is not UNSET:
            field_dict["private"] = private
        if review_notes is not UNSET:
            field_dict["review_notes"] = review_notes
        if reviewed_at is not UNSET:
            field_dict["reviewed_at"] = reviewed_at
        if reviewer is not UNSET:
            field_dict["reviewer"] = reviewer
        if revised_substantial_completion_date is not UNSET:
            field_dict["revised_substantial_completion_date"] = (
                revised_substantial_completion_date
            )
        if revision is not UNSET:
            field_dict["revision"] = revision
        if schedule_impact_amount is not UNSET:
            field_dict["schedule_impact_amount"] = schedule_impact_amount
        if signed_change_order_received_date is not UNSET:
            field_dict["signed_change_order_received_date"] = (
                signed_change_order_received_date
            )
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_order_package_attachments_item import (
            ProcoreChangeOrderPackageAttachmentsItem,
        )
        from ..models.procore_change_order_package_creator import (
            ProcoreChangeOrderPackageCreator,
        )
        from ..models.procore_change_order_package_currency_configuration import (
            ProcoreChangeOrderPackageCurrencyConfiguration,
        )
        from ..models.procore_change_order_package_custom_fields import (
            ProcoreChangeOrderPackageCustomFields,
        )
        from ..models.procore_change_order_package_designated_reviewer import (
            ProcoreChangeOrderPackageDesignatedReviewer,
        )
        from ..models.procore_change_order_package_line_items_item import (
            ProcoreChangeOrderPackageLineItemsItem,
        )
        from ..models.procore_change_order_package_reviewer import (
            ProcoreChangeOrderPackageReviewer,
        )

        d = dict(src_dict)
        _attachments = d.pop("attachments", UNSET)
        attachments: list[ProcoreChangeOrderPackageAttachmentsItem] | Unset = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = ProcoreChangeOrderPackageAttachmentsItem.from_dict(
                    attachments_item_data
                )

                attachments.append(attachments_item)

        contract_id = d.pop("contract_id", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _creator = d.pop("creator", UNSET)
        creator: ProcoreChangeOrderPackageCreator | Unset
        if isinstance(_creator, Unset):
            creator = UNSET
        else:
            creator = ProcoreChangeOrderPackageCreator.from_dict(_creator)

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: ProcoreChangeOrderPackageCurrencyConfiguration | Unset
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = (
                ProcoreChangeOrderPackageCurrencyConfiguration.from_dict(
                    _currency_configuration
                )
            )

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: ProcoreChangeOrderPackageCustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = ProcoreChangeOrderPackageCustomFields.from_dict(
                _custom_fields
            )

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        description = d.pop("description", UNSET)

        _designated_reviewer = d.pop("designated_reviewer", UNSET)
        designated_reviewer: ProcoreChangeOrderPackageDesignatedReviewer | Unset
        if isinstance(_designated_reviewer, Unset):
            designated_reviewer = UNSET
        else:
            designated_reviewer = ProcoreChangeOrderPackageDesignatedReviewer.from_dict(
                _designated_reviewer
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

        _line_items = d.pop("line_items", UNSET)
        line_items: list[ProcoreChangeOrderPackageLineItemsItem] | Unset = UNSET
        if _line_items is not UNSET:
            line_items = []
            for line_items_item_data in _line_items:
                line_items_item = ProcoreChangeOrderPackageLineItemsItem.from_dict(
                    line_items_item_data
                )

                line_items.append(line_items_item)

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

        position = d.pop("position", UNSET)

        private = d.pop("private", UNSET)

        review_notes = d.pop("review_notes", UNSET)

        _reviewed_at = d.pop("reviewed_at", UNSET)
        reviewed_at: datetime.datetime | Unset
        if isinstance(_reviewed_at, Unset):
            reviewed_at = UNSET
        else:
            reviewed_at = datetime.datetime.fromisoformat(_reviewed_at)

        _reviewer = d.pop("reviewer", UNSET)
        reviewer: ProcoreChangeOrderPackageReviewer | Unset
        if isinstance(_reviewer, Unset):
            reviewer = UNSET
        else:
            reviewer = ProcoreChangeOrderPackageReviewer.from_dict(_reviewer)

        _revised_substantial_completion_date = d.pop(
            "revised_substantial_completion_date", UNSET
        )
        revised_substantial_completion_date: datetime.date | Unset
        if isinstance(_revised_substantial_completion_date, Unset):
            revised_substantial_completion_date = UNSET
        else:
            revised_substantial_completion_date = datetime.date.fromisoformat(
                _revised_substantial_completion_date
            )

        revision = d.pop("revision", UNSET)

        schedule_impact_amount = d.pop("schedule_impact_amount", UNSET)

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
        status: ProcoreChangeOrderPackageStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ProcoreChangeOrderPackageStatus(_status)

        title = d.pop("title", UNSET)

        _type_ = d.pop("type", UNSET)
        type_: ProcoreChangeOrderPackageType | Unset
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = ProcoreChangeOrderPackageType(_type_)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        procore_change_order_package = cls(
            attachments=attachments,
            contract_id=contract_id,
            created_at=created_at,
            creator=creator,
            currency_configuration=currency_configuration,
            custom_fields=custom_fields,
            deleted_at=deleted_at,
            description=description,
            designated_reviewer=designated_reviewer,
            due_date=due_date,
            executed=executed,
            grand_total=grand_total,
            id=id,
            invoiced_date=invoiced_date,
            line_items=line_items,
            number=number,
            origin_code=origin_code,
            origin_data=origin_data,
            origin_id=origin_id,
            paid_date=paid_date,
            position=position,
            private=private,
            review_notes=review_notes,
            reviewed_at=reviewed_at,
            reviewer=reviewer,
            revised_substantial_completion_date=revised_substantial_completion_date,
            revision=revision,
            schedule_impact_amount=schedule_impact_amount,
            signed_change_order_received_date=signed_change_order_received_date,
            status=status,
            title=title,
            type_=type_,
            updated_at=updated_at,
        )

        procore_change_order_package.additional_properties = d
        return procore_change_order_package

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
