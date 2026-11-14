from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_body_change_event_scope import (
    CreateChangeEventBodyChangeEventScope,
)
from ..models.create_change_event_body_change_event_source import (
    CreateChangeEventBodyChangeEventSource,
)
from ..models.create_change_event_body_change_event_source_of_revenue_rom import (
    CreateChangeEventBodyChangeEventSourceOfRevenueRom,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_body_change_event_change_items_item import (
        CreateChangeEventBodyChangeEventChangeItemsItem,
    )
    from ..models.create_change_event_body_change_event_change_reason import (
        CreateChangeEventBodyChangeEventChangeReason,
    )
    from ..models.create_change_event_body_change_event_change_type import (
        CreateChangeEventBodyChangeEventChangeType,
    )
    from ..models.create_change_event_body_change_event_event_origin_type_0 import (
        CreateChangeEventBodyChangeEventEventOriginType0,
    )
    from ..models.create_change_event_body_change_event_external_data import (
        CreateChangeEventBodyChangeEventExternalData,
    )
    from ..models.create_change_event_body_change_event_prime_contract_for_estimates import (
        CreateChangeEventBodyChangeEventPrimeContractForEstimates,
    )
    from ..models.create_change_event_body_change_event_status import (
        CreateChangeEventBodyChangeEventStatus,
    )


T = TypeVar("T", bound="CreateChangeEventBodyChangeEvent")


@_attrs_define
class CreateChangeEventBodyChangeEvent:
    """
    Attributes:
        scope (CreateChangeEventBodyChangeEventScope): Scope classification of the Change Event.
        status (CreateChangeEventBodyChangeEventStatus):
        change_items (list[CreateChangeEventBodyChangeEventChangeItemsItem] | Unset): Change Event Line Items
        change_reason (CreateChangeEventBodyChangeEventChangeReason | Unset):
        change_type (CreateChangeEventBodyChangeEventChangeType | Unset):
        description (str | Unset): Detailed description of the work or reason for the Change Event.
        event_origin (CreateChangeEventBodyChangeEventEventOriginType0 | None | Unset):
        external_data (CreateChangeEventBodyChangeEventExternalData | Unset):
        number (str | Unset): User-defined identifier for the Change Event (may include alphanumeric characters). If
            omitted on create, one is auto-assigned.
        prime_contract_for_estimates (CreateChangeEventBodyChangeEventPrimeContractForEstimates | Unset):
        source (CreateChangeEventBodyChangeEventSource | Unset): The Change Event source refers to the resource that was
            responsible for creating this Change Event.
        source_of_revenue_rom (CreateChangeEventBodyChangeEventSourceOfRevenueRom | Unset): Revenue ROM source for this
            Change Event
        title (str | Unset): Human-readable title summarizing the Change Event.
    """

    scope: CreateChangeEventBodyChangeEventScope
    status: CreateChangeEventBodyChangeEventStatus
    change_items: list[CreateChangeEventBodyChangeEventChangeItemsItem] | Unset = UNSET
    change_reason: CreateChangeEventBodyChangeEventChangeReason | Unset = UNSET
    change_type: CreateChangeEventBodyChangeEventChangeType | Unset = UNSET
    description: str | Unset = UNSET
    event_origin: CreateChangeEventBodyChangeEventEventOriginType0 | None | Unset = (
        UNSET
    )
    external_data: CreateChangeEventBodyChangeEventExternalData | Unset = UNSET
    number: str | Unset = UNSET
    prime_contract_for_estimates: (
        CreateChangeEventBodyChangeEventPrimeContractForEstimates | Unset
    ) = UNSET
    source: CreateChangeEventBodyChangeEventSource | Unset = UNSET
    source_of_revenue_rom: (
        CreateChangeEventBodyChangeEventSourceOfRevenueRom | Unset
    ) = UNSET
    title: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_change_event_body_change_event_event_origin_type_0 import (
            CreateChangeEventBodyChangeEventEventOriginType0,
        )

        scope = self.scope.value

        status = self.status.to_dict()

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

        description = self.description

        event_origin: dict[str, Any] | None | Unset
        if isinstance(self.event_origin, Unset):
            event_origin = UNSET
        elif isinstance(
            self.event_origin, CreateChangeEventBodyChangeEventEventOriginType0
        ):
            event_origin = self.event_origin.to_dict()
        else:
            event_origin = self.event_origin

        external_data: dict[str, Any] | Unset = UNSET
        if not isinstance(self.external_data, Unset):
            external_data = self.external_data.to_dict()

        number = self.number

        prime_contract_for_estimates: dict[str, Any] | Unset = UNSET
        if not isinstance(self.prime_contract_for_estimates, Unset):
            prime_contract_for_estimates = self.prime_contract_for_estimates.to_dict()

        source: str | Unset = UNSET
        if not isinstance(self.source, Unset):
            source = self.source.value

        source_of_revenue_rom: str | Unset = UNSET
        if not isinstance(self.source_of_revenue_rom, Unset):
            source_of_revenue_rom = self.source_of_revenue_rom.value

        title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "scope": scope,
                "status": status,
            }
        )
        if change_items is not UNSET:
            field_dict["change_items"] = change_items
        if change_reason is not UNSET:
            field_dict["change_reason"] = change_reason
        if change_type is not UNSET:
            field_dict["change_type"] = change_type
        if description is not UNSET:
            field_dict["description"] = description
        if event_origin is not UNSET:
            field_dict["event_origin"] = event_origin
        if external_data is not UNSET:
            field_dict["external_data"] = external_data
        if number is not UNSET:
            field_dict["number"] = number
        if prime_contract_for_estimates is not UNSET:
            field_dict["prime_contract_for_estimates"] = prime_contract_for_estimates
        if source is not UNSET:
            field_dict["source"] = source
        if source_of_revenue_rom is not UNSET:
            field_dict["source_of_revenue_rom"] = source_of_revenue_rom
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_body_change_event_change_items_item import (
            CreateChangeEventBodyChangeEventChangeItemsItem,
        )
        from ..models.create_change_event_body_change_event_change_reason import (
            CreateChangeEventBodyChangeEventChangeReason,
        )
        from ..models.create_change_event_body_change_event_change_type import (
            CreateChangeEventBodyChangeEventChangeType,
        )
        from ..models.create_change_event_body_change_event_event_origin_type_0 import (
            CreateChangeEventBodyChangeEventEventOriginType0,
        )
        from ..models.create_change_event_body_change_event_external_data import (
            CreateChangeEventBodyChangeEventExternalData,
        )
        from ..models.create_change_event_body_change_event_prime_contract_for_estimates import (
            CreateChangeEventBodyChangeEventPrimeContractForEstimates,
        )
        from ..models.create_change_event_body_change_event_status import (
            CreateChangeEventBodyChangeEventStatus,
        )

        d = dict(src_dict)
        scope = CreateChangeEventBodyChangeEventScope(d.pop("scope"))

        status = CreateChangeEventBodyChangeEventStatus.from_dict(d.pop("status"))

        _change_items = d.pop("change_items", UNSET)
        change_items: list[CreateChangeEventBodyChangeEventChangeItemsItem] | Unset = (
            UNSET
        )
        if _change_items is not UNSET:
            change_items = []
            for change_items_item_data in _change_items:
                change_items_item = (
                    CreateChangeEventBodyChangeEventChangeItemsItem.from_dict(
                        change_items_item_data
                    )
                )

                change_items.append(change_items_item)

        _change_reason = d.pop("change_reason", UNSET)
        change_reason: CreateChangeEventBodyChangeEventChangeReason | Unset
        if isinstance(_change_reason, Unset):
            change_reason = UNSET
        else:
            change_reason = CreateChangeEventBodyChangeEventChangeReason.from_dict(
                _change_reason
            )

        _change_type = d.pop("change_type", UNSET)
        change_type: CreateChangeEventBodyChangeEventChangeType | Unset
        if isinstance(_change_type, Unset):
            change_type = UNSET
        else:
            change_type = CreateChangeEventBodyChangeEventChangeType.from_dict(
                _change_type
            )

        description = d.pop("description", UNSET)

        def _parse_event_origin(
            data: object,
        ) -> CreateChangeEventBodyChangeEventEventOriginType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                event_origin_type_0 = (
                    CreateChangeEventBodyChangeEventEventOriginType0.from_dict(data)
                )

                return event_origin_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventBodyChangeEventEventOriginType0 | None | Unset, data
            )

        event_origin = _parse_event_origin(d.pop("event_origin", UNSET))

        _external_data = d.pop("external_data", UNSET)
        external_data: CreateChangeEventBodyChangeEventExternalData | Unset
        if isinstance(_external_data, Unset):
            external_data = UNSET
        else:
            external_data = CreateChangeEventBodyChangeEventExternalData.from_dict(
                _external_data
            )

        number = d.pop("number", UNSET)

        _prime_contract_for_estimates = d.pop("prime_contract_for_estimates", UNSET)
        prime_contract_for_estimates: (
            CreateChangeEventBodyChangeEventPrimeContractForEstimates | Unset
        )
        if isinstance(_prime_contract_for_estimates, Unset):
            prime_contract_for_estimates = UNSET
        else:
            prime_contract_for_estimates = (
                CreateChangeEventBodyChangeEventPrimeContractForEstimates.from_dict(
                    _prime_contract_for_estimates
                )
            )

        _source = d.pop("source", UNSET)
        source: CreateChangeEventBodyChangeEventSource | Unset
        if isinstance(_source, Unset):
            source = UNSET
        else:
            source = CreateChangeEventBodyChangeEventSource(_source)

        _source_of_revenue_rom = d.pop("source_of_revenue_rom", UNSET)
        source_of_revenue_rom: (
            CreateChangeEventBodyChangeEventSourceOfRevenueRom | Unset
        )
        if isinstance(_source_of_revenue_rom, Unset):
            source_of_revenue_rom = UNSET
        else:
            source_of_revenue_rom = CreateChangeEventBodyChangeEventSourceOfRevenueRom(
                _source_of_revenue_rom
            )

        title = d.pop("title", UNSET)

        create_change_event_body_change_event = cls(
            scope=scope,
            status=status,
            change_items=change_items,
            change_reason=change_reason,
            change_type=change_type,
            description=description,
            event_origin=event_origin,
            external_data=external_data,
            number=number,
            prime_contract_for_estimates=prime_contract_for_estimates,
            source=source,
            source_of_revenue_rom=source_of_revenue_rom,
            title=title,
        )

        create_change_event_body_change_event.additional_properties = d
        return create_change_event_body_change_event

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
