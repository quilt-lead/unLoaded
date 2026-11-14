from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_contract_type import (
    ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0ContractType,
)
from ..models.list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_type import (
    ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0Type,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_currency_configuration import (
        ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration,
    )
    from ..models.list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_line_item import (
        ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem,
    )


T = TypeVar(
    "T", bound="ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0"
)


@_attrs_define
class ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0:
    """
    Attributes:
        contract_type (ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0ContractType | Unset): The
            type of the contract associated with the Commitment
        currency_configuration
            (ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration | Unset): Currency
            configuration information for the Commitment
        days_in_stage (int | Unset): Number of days since Change Event Line Item was associated with Commitment Contract
            or Commitment PCO and until Change Event was closed (or until today if it wasn't)
        id (int | Unset): ID of the Commitment
        in_status_since (datetime.datetime | None | Unset): Last time this status was updated
        line_item (ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem | Unset):
        number (str | Unset): Number of the Commitment Contract or Change Order
        status (None | str | Unset): Status of the Commitment
        title (None | str | Unset): Commitment title
        type_ (ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0Type | Unset): Type of Commitment
    """

    contract_type: (
        ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0ContractType
        | Unset
    ) = UNSET
    currency_configuration: (
        ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration
        | Unset
    ) = UNSET
    days_in_stage: int | Unset = UNSET
    id: int | Unset = UNSET
    in_status_since: datetime.datetime | None | Unset = UNSET
    line_item: (
        ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem
        | Unset
    ) = UNSET
    number: str | Unset = UNSET
    status: None | str | Unset = UNSET
    title: None | str | Unset = UNSET
    type_: (
        ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0Type
        | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        contract_type: str | Unset = UNSET
        if not isinstance(self.contract_type, Unset):
            contract_type = self.contract_type.value

        currency_configuration: dict[str, Any] | Unset = UNSET
        if not isinstance(self.currency_configuration, Unset):
            currency_configuration = self.currency_configuration.to_dict()

        days_in_stage = self.days_in_stage

        id = self.id

        in_status_since: None | str | Unset
        if isinstance(self.in_status_since, Unset):
            in_status_since = UNSET
        elif isinstance(self.in_status_since, datetime.datetime):
            in_status_since = self.in_status_since.isoformat()
        else:
            in_status_since = self.in_status_since

        line_item: dict[str, Any] | Unset = UNSET
        if not isinstance(self.line_item, Unset):
            line_item = self.line_item.to_dict()

        number = self.number

        status: None | str | Unset
        if isinstance(self.status, Unset):
            status = UNSET
        else:
            status = self.status

        title: None | str | Unset
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if contract_type is not UNSET:
            field_dict["contract_type"] = contract_type
        if currency_configuration is not UNSET:
            field_dict["currency_configuration"] = currency_configuration
        if days_in_stage is not UNSET:
            field_dict["days_in_stage"] = days_in_stage
        if id is not UNSET:
            field_dict["id"] = id
        if in_status_since is not UNSET:
            field_dict["in_status_since"] = in_status_since
        if line_item is not UNSET:
            field_dict["line_item"] = line_item
        if number is not UNSET:
            field_dict["number"] = number
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_currency_configuration import (
            ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration,
        )
        from ..models.list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0_line_item import (
            ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem,
        )

        d = dict(src_dict)
        _contract_type = d.pop("contract_type", UNSET)
        contract_type: (
            ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0ContractType
            | Unset
        )
        if isinstance(_contract_type, Unset):
            contract_type = UNSET
        else:
            contract_type = ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0ContractType(
                _contract_type
            )

        _currency_configuration = d.pop("currency_configuration", UNSET)
        currency_configuration: (
            ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration
            | Unset
        )
        if isinstance(_currency_configuration, Unset):
            currency_configuration = UNSET
        else:
            currency_configuration = ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0CurrencyConfiguration.from_dict(
                _currency_configuration
            )

        days_in_stage = d.pop("days_in_stage", UNSET)

        id = d.pop("id", UNSET)

        def _parse_in_status_since(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                in_status_since_type_0 = datetime.datetime.fromisoformat(data)

                return in_status_since_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        in_status_since = _parse_in_status_since(d.pop("in_status_since", UNSET))

        _line_item = d.pop("line_item", UNSET)
        line_item: (
            ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem
            | Unset
        )
        if isinstance(_line_item, Unset):
            line_item = UNSET
        else:
            line_item = ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0LineItem.from_dict(
                _line_item
            )

        number = d.pop("number", UNSET)

        def _parse_status(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        status = _parse_status(d.pop("status", UNSET))

        def _parse_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title = _parse_title(d.pop("title", UNSET))

        _type_ = d.pop("type", UNSET)
        type_: (
            ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0Type
            | Unset
        )
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = ListChangeEventsResponse200ItemChangeItemsItemCostImpactCommitmentType0Type(
                _type_
            )

        list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0 = cls(
            contract_type=contract_type,
            currency_configuration=currency_configuration,
            days_in_stage=days_in_stage,
            id=id,
            in_status_since=in_status_since,
            line_item=line_item,
            number=number,
            status=status,
            title=title,
            type_=type_,
        )

        list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0.additional_properties = d
        return list_change_events_response_200_item_change_items_item_cost_impact_commitment_type_0

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
