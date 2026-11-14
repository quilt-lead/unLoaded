from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.get_change_event_response_200_source import (
    GetChangeEventResponse200Source,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.get_change_event_response_200_attachments_item import (
        GetChangeEventResponse200AttachmentsItem,
    )
    from ..models.get_change_event_response_200_change_items_item import (
        GetChangeEventResponse200ChangeItemsItem,
    )
    from ..models.get_change_event_response_200_change_reason import (
        GetChangeEventResponse200ChangeReason,
    )
    from ..models.get_change_event_response_200_change_type import (
        GetChangeEventResponse200ChangeType,
    )
    from ..models.get_change_event_response_200_created_by import (
        GetChangeEventResponse200CreatedBy,
    )
    from ..models.get_change_event_response_200_currency_configuration import (
        GetChangeEventResponse200CurrencyConfiguration,
    )
    from ..models.get_change_event_response_200_custom_fields import (
        GetChangeEventResponse200CustomFields,
    )
    from ..models.get_change_event_response_200_event_origin import (
        GetChangeEventResponse200EventOrigin,
    )
    from ..models.get_change_event_response_200_external_data import (
        GetChangeEventResponse200ExternalData,
    )
    from ..models.get_change_event_response_200_markup_items_item import (
        GetChangeEventResponse200MarkupItemsItem,
    )
    from ..models.get_change_event_response_200_notes import (
        GetChangeEventResponse200Notes,
    )
    from ..models.get_change_event_response_200_prime_contract_for_estimates import (
        GetChangeEventResponse200PrimeContractForEstimates,
    )
    from ..models.get_change_event_response_200_production_quantities_item import (
        GetChangeEventResponse200ProductionQuantitiesItem,
    )
    from ..models.get_change_event_response_200_status import (
        GetChangeEventResponse200Status,
    )


T = TypeVar("T", bound="GetChangeEventResponse200")


@_attrs_define
class GetChangeEventResponse200:
    """
    Attributes:
        attachments (list[GetChangeEventResponse200AttachmentsItem] | Unset):
        change_items (list[GetChangeEventResponse200ChangeItemsItem] | Unset):
        change_reason (GetChangeEventResponse200ChangeReason | Unset):
        change_type (GetChangeEventResponse200ChangeType | Unset):
        comments_enabled (bool | Unset): Comments Enabled
        company_id (int | Unset): unique identifier for the company
        created_at (datetime.datetime | Unset):
        created_by (GetChangeEventResponse200CreatedBy | Unset):
        currency_configuration (GetChangeEventResponse200CurrencyConfiguration | Unset): currency configuration
            information
        custom_fields (GetChangeEventResponse200CustomFields | Unset):
        deletable (bool | Unset):
        deleted_at (datetime.datetime | Unset):
        description (str | Unset): description
        event_origin (GetChangeEventResponse200EventOrigin | Unset):
        external_data (GetChangeEventResponse200ExternalData | Unset):
        id (int | Unset): ID
        in_recycle_bin (bool | Unset):
        markup_items (list[GetChangeEventResponse200MarkupItemsItem] | Unset): markup items
        notes (GetChangeEventResponse200Notes | Unset): The failures of independent actions will be aggregated under the
            attribute and will not result in a Failure. For example: sync WBS code.
        number (str | Unset): number
        prime_contract_for_estimates (GetChangeEventResponse200PrimeContractForEstimates | Unset):
        production_quantities (list[GetChangeEventResponse200ProductionQuantitiesItem] | Unset): change event related
            production quantities
        project_id (int | Unset): unique identifier for the project
        scope (str | Unset): scope
        source (GetChangeEventResponse200Source | Unset): The Change Event source refers to the resource that was
            responsible for creating this Change Event.
        status (GetChangeEventResponse200Status | Unset):
        title (str | Unset): title
        updated_at (datetime.datetime | Unset):
    """

    attachments: list[GetChangeEventResponse200AttachmentsItem] | Unset = UNSET
    change_items: list[GetChangeEventResponse200ChangeItemsItem] | Unset = UNSET
    change_reason: GetChangeEventResponse200ChangeReason | Unset = UNSET
    change_type: GetChangeEventResponse200ChangeType | Unset = UNSET
    comments_enabled: bool | Unset = UNSET
    company_id: int | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: GetChangeEventResponse200CreatedBy | Unset = UNSET
    currency_configuration: GetChangeEventResponse200CurrencyConfiguration | Unset = (
        UNSET
    )
    custom_fields: GetChangeEventResponse200CustomFields | Unset = UNSET
    deletable: bool | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    description: str | Unset = UNSET
    event_origin: GetChangeEventResponse200EventOrigin | Unset = UNSET
    external_data: GetChangeEventResponse200ExternalData | Unset = UNSET
    id: int | Unset = UNSET
    in_recycle_bin: bool | Unset = UNSET
    markup_items: list[GetChangeEventResponse200MarkupItemsItem] | Unset = UNSET
    notes: GetChangeEventResponse200Notes | Unset = UNSET
    number: str | Unset = UNSET
    prime_contract_for_estimates: (
        GetChangeEventResponse200PrimeContractForEstimates | Unset
    ) = UNSET
    production_quantities: (
        list[GetChangeEventResponse200ProductionQuantitiesItem] | Unset
    ) = UNSET
    project_id: int | Unset = UNSET
    scope: str | Unset = UNSET
    source: GetChangeEventResponse200Source | Unset = UNSET
    status: GetChangeEventResponse200Status | Unset = UNSET
    title: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        change_items: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.change_items, Unset):
            change_items = []
            for change_items_item_data in self.change_items:
                change_items_item = change_items_item_data.to_dict()
                change_items.append(change_items_item)

        change_reason: dict[str, Any] | Unset = UNSET
        if not isinstance(self.change_reason, Unset):
            change_reason = self.change_reason.to_dict()

        change_type: dict[str, Any] | Unset = UNSET
        if not isinstance(self.change_type, Unset):
            change_type = self.change_type.to_dict()

        comments_enabled = self.comments_enabled

        company_id = self.company_id

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        created_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.created_by, Unset):
            created_by = self.created_by.to_dict()

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        custom_fields: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_fields, Unset):
            custom_fields = self.custom_fields.to_dict()

        deletable = self.deletable

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        description = self.description

        event_origin: dict[str, Any] | Unset = UNSET
        if not isinstance(self.event_origin, Unset):
            event_origin = self.event_origin.to_dict()

        external_data: dict[str, Any] | Unset = UNSET
        if not isinstance(self.external_data, Unset):
            external_data = self.external_data.to_dict()

        id = self.id

        in_recycle_bin = self.in_recycle_bin

        markup_items: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.markup_items, Unset):
            markup_items = []
            for markup_items_item_data in self.markup_items:
                markup_items_item = markup_items_item_data.to_dict()
                markup_items.append(markup_items_item)

        notes: dict[str, Any] | Unset = UNSET
        if not isinstance(self.notes, Unset):
            notes = self.notes.to_dict()

        number = self.number

        prime_contract_for_estimates: dict[str, Any] | Unset = UNSET
        if not isinstance(self.prime_contract_for_estimates, Unset):
            prime_contract_for_estimates = self.prime_contract_for_estimates.to_dict()

        production_quantities: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.production_quantities, Unset):
            production_quantities = []
            for production_quantities_item_data in self.production_quantities:
                production_quantities_item = production_quantities_item_data.to_dict()
                production_quantities.append(production_quantities_item)

        project_id = self.project_id

        scope = self.scope

        source: str | Unset = UNSET
        if not isinstance(self.source, Unset):
            source = self.source.value

        status: dict[str, Any] | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.to_dict()

        title = self.title

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if change_items is not UNSET:
            field_dict["change_items"] = change_items
        if change_reason is not UNSET:
            field_dict["change_reason"] = change_reason
        if change_type is not UNSET:
            field_dict["change_type"] = change_type
        if comments_enabled is not UNSET:
            field_dict["comments_enabled"] = comments_enabled
        if company_id is not UNSET:
            field_dict["company_id"] = company_id
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if deletable is not UNSET:
            field_dict["deletable"] = deletable
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if description is not UNSET:
            field_dict["description"] = description
        if event_origin is not UNSET:
            field_dict["event_origin"] = event_origin
        if external_data is not UNSET:
            field_dict["external_data"] = external_data
        if id is not UNSET:
            field_dict["id"] = id
        if in_recycle_bin is not UNSET:
            field_dict["in_recycle_bin"] = in_recycle_bin
        if markup_items is not UNSET:
            field_dict["markup_items"] = markup_items
        if notes is not UNSET:
            field_dict["notes"] = notes
        if number is not UNSET:
            field_dict["number"] = number
        if prime_contract_for_estimates is not UNSET:
            field_dict["prime_contract_for_estimates"] = prime_contract_for_estimates
        if production_quantities is not UNSET:
            field_dict["production_quantities"] = production_quantities
        if project_id is not UNSET:
            field_dict["project_id"] = project_id
        if scope is not UNSET:
            field_dict["scope"] = scope
        if source is not UNSET:
            field_dict["source"] = source
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.get_change_event_response_200_attachments_item import (
            GetChangeEventResponse200AttachmentsItem,
        )
        from ..models.get_change_event_response_200_change_items_item import (
            GetChangeEventResponse200ChangeItemsItem,
        )
        from ..models.get_change_event_response_200_change_reason import (
            GetChangeEventResponse200ChangeReason,
        )
        from ..models.get_change_event_response_200_change_type import (
            GetChangeEventResponse200ChangeType,
        )
        from ..models.get_change_event_response_200_created_by import (
            GetChangeEventResponse200CreatedBy,
        )
        from ..models.get_change_event_response_200_currency_configuration import (
            GetChangeEventResponse200CurrencyConfiguration,
        )
        from ..models.get_change_event_response_200_custom_fields import (
            GetChangeEventResponse200CustomFields,
        )
        from ..models.get_change_event_response_200_event_origin import (
            GetChangeEventResponse200EventOrigin,
        )
        from ..models.get_change_event_response_200_external_data import (
            GetChangeEventResponse200ExternalData,
        )
        from ..models.get_change_event_response_200_markup_items_item import (
            GetChangeEventResponse200MarkupItemsItem,
        )
        from ..models.get_change_event_response_200_notes import (
            GetChangeEventResponse200Notes,
        )
        from ..models.get_change_event_response_200_prime_contract_for_estimates import (
            GetChangeEventResponse200PrimeContractForEstimates,
        )
        from ..models.get_change_event_response_200_production_quantities_item import (
            GetChangeEventResponse200ProductionQuantitiesItem,
        )
        from ..models.get_change_event_response_200_status import (
            GetChangeEventResponse200Status,
        )

        d = dict(src_dict)
        _attachments = d.pop("attachments", UNSET)
        attachments: list[GetChangeEventResponse200AttachmentsItem] | Unset = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = GetChangeEventResponse200AttachmentsItem.from_dict(
                    attachments_item_data
                )

                attachments.append(attachments_item)

        _change_items = d.pop("change_items", UNSET)
        change_items: list[GetChangeEventResponse200ChangeItemsItem] | Unset = UNSET
        if _change_items is not UNSET:
            change_items = []
            for change_items_item_data in _change_items:
                change_items_item = GetChangeEventResponse200ChangeItemsItem.from_dict(
                    change_items_item_data
                )

                change_items.append(change_items_item)

        _change_reason = d.pop("change_reason", UNSET)
        change_reason: GetChangeEventResponse200ChangeReason | Unset
        if isinstance(_change_reason, Unset):
            change_reason = UNSET
        else:
            change_reason = GetChangeEventResponse200ChangeReason.from_dict(
                _change_reason
            )

        _change_type = d.pop("change_type", UNSET)
        change_type: GetChangeEventResponse200ChangeType | Unset
        if isinstance(_change_type, Unset):
            change_type = UNSET
        else:
            change_type = GetChangeEventResponse200ChangeType.from_dict(_change_type)

        comments_enabled = d.pop("comments_enabled", UNSET)

        company_id = d.pop("company_id", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _created_by = d.pop("created_by", UNSET)
        created_by: GetChangeEventResponse200CreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = GetChangeEventResponse200CreatedBy.from_dict(_created_by)

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: GetChangeEventResponse200CurrencyConfiguration | Unset
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = (
                GetChangeEventResponse200CurrencyConfiguration.from_dict(
                    _currency_configuration
                )
            )

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: GetChangeEventResponse200CustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = GetChangeEventResponse200CustomFields.from_dict(
                _custom_fields
            )

        deletable = d.pop("deletable", UNSET)

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        description = d.pop("description", UNSET)

        _event_origin = d.pop("event_origin", UNSET)
        event_origin: GetChangeEventResponse200EventOrigin | Unset
        if isinstance(_event_origin, Unset):
            event_origin = UNSET
        else:
            event_origin = GetChangeEventResponse200EventOrigin.from_dict(_event_origin)

        _external_data = d.pop("external_data", UNSET)
        external_data: GetChangeEventResponse200ExternalData | Unset
        if isinstance(_external_data, Unset):
            external_data = UNSET
        else:
            external_data = GetChangeEventResponse200ExternalData.from_dict(
                _external_data
            )

        id = d.pop("id", UNSET)

        in_recycle_bin = d.pop("in_recycle_bin", UNSET)

        _markup_items = d.pop("markup_items", UNSET)
        markup_items: list[GetChangeEventResponse200MarkupItemsItem] | Unset = UNSET
        if _markup_items is not UNSET:
            markup_items = []
            for markup_items_item_data in _markup_items:
                markup_items_item = GetChangeEventResponse200MarkupItemsItem.from_dict(
                    markup_items_item_data
                )

                markup_items.append(markup_items_item)

        _notes = d.pop("notes", UNSET)
        notes: GetChangeEventResponse200Notes | Unset
        if isinstance(_notes, Unset):
            notes = UNSET
        else:
            notes = GetChangeEventResponse200Notes.from_dict(_notes)

        number = d.pop("number", UNSET)

        _prime_contract_for_estimates = d.pop("prime_contract_for_estimates", UNSET)
        prime_contract_for_estimates: (
            GetChangeEventResponse200PrimeContractForEstimates | Unset
        )
        if isinstance(_prime_contract_for_estimates, Unset):
            prime_contract_for_estimates = UNSET
        else:
            prime_contract_for_estimates = (
                GetChangeEventResponse200PrimeContractForEstimates.from_dict(
                    _prime_contract_for_estimates
                )
            )

        _production_quantities = d.pop("production_quantities", UNSET)
        production_quantities: (
            list[GetChangeEventResponse200ProductionQuantitiesItem] | Unset
        ) = UNSET
        if _production_quantities is not UNSET:
            production_quantities = []
            for production_quantities_item_data in _production_quantities:
                production_quantities_item = (
                    GetChangeEventResponse200ProductionQuantitiesItem.from_dict(
                        production_quantities_item_data
                    )
                )

                production_quantities.append(production_quantities_item)

        project_id = d.pop("project_id", UNSET)

        scope = d.pop("scope", UNSET)

        _source = d.pop("source", UNSET)
        source: GetChangeEventResponse200Source | Unset
        if isinstance(_source, Unset):
            source = UNSET
        else:
            source = GetChangeEventResponse200Source(_source)

        _status = d.pop("status", UNSET)
        status: GetChangeEventResponse200Status | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = GetChangeEventResponse200Status.from_dict(_status)

        title = d.pop("title", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        get_change_event_response_200 = cls(
            attachments=attachments,
            change_items=change_items,
            change_reason=change_reason,
            change_type=change_type,
            comments_enabled=comments_enabled,
            company_id=company_id,
            created_at=created_at,
            created_by=created_by,
            currency_configuration=currency_configuration,
            custom_fields=custom_fields,
            deletable=deletable,
            deleted_at=deleted_at,
            description=description,
            event_origin=event_origin,
            external_data=external_data,
            id=id,
            in_recycle_bin=in_recycle_bin,
            markup_items=markup_items,
            notes=notes,
            number=number,
            prime_contract_for_estimates=prime_contract_for_estimates,
            production_quantities=production_quantities,
            project_id=project_id,
            scope=scope,
            source=source,
            status=status,
            title=title,
            updated_at=updated_at,
        )

        get_change_event_response_200.additional_properties = d
        return get_change_event_response_200

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
