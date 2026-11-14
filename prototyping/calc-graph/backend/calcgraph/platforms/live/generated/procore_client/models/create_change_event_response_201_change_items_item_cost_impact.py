from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_change_items_item_cost_impact_source_of_latest_cost import (
    CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfLatestCost,
)
from ..models.create_change_event_response_201_change_items_item_cost_impact_source_of_stage import (
    CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfStage,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_change_items_item_cost_impact_change_order_package_type_0 import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0,
    )
    from ..models.create_change_event_response_201_change_items_item_cost_impact_commitment_type_0 import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0,
    )
    from ..models.create_change_event_response_201_change_items_item_cost_impact_contract import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactContract,
    )
    from ..models.create_change_event_response_201_change_items_item_cost_impact_estimate import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate,
    )
    from ..models.create_change_event_response_201_change_items_item_cost_impact_non_commitment import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactNonCommitment,
    )
    from ..models.create_change_event_response_201_change_items_item_cost_impact_request_for_quote_type_0 import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0,
    )
    from ..models.create_change_event_response_201_change_items_item_cost_impact_vendor import (
        CreateChangeEventResponse201ChangeItemsItemCostImpactVendor,
    )


T = TypeVar("T", bound="CreateChangeEventResponse201ChangeItemsItemCostImpact")


@_attrs_define
class CreateChangeEventResponse201ChangeItemsItemCostImpact:
    """
    Attributes:
        change_order_package (CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0 | None |
            Unset):
        commitment (CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0 | None | Unset):
        contract (CreateChangeEventResponse201ChangeItemsItemCostImpactContract | Unset):
        estimate (CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate | Unset):
        non_commitment (CreateChangeEventResponse201ChangeItemsItemCostImpactNonCommitment | Unset):
        request_for_quote (CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0 | None | Unset):
            Request for Quote data if any present, can be null
        source_of_latest_cost (CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfLatestCost | Unset): Source
            of latest cost
        source_of_stage (CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfStage | Unset): Source of stage
        vendor (CreateChangeEventResponse201ChangeItemsItemCostImpactVendor | Unset):
    """

    change_order_package: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0
        | None
        | Unset
    ) = UNSET
    commitment: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0
        | None
        | Unset
    ) = UNSET
    contract: CreateChangeEventResponse201ChangeItemsItemCostImpactContract | Unset = (
        UNSET
    )
    estimate: CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate | Unset = (
        UNSET
    )
    non_commitment: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactNonCommitment | Unset
    ) = UNSET
    request_for_quote: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0
        | None
        | Unset
    ) = UNSET
    source_of_latest_cost: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfLatestCost | Unset
    ) = UNSET
    source_of_stage: (
        CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfStage | Unset
    ) = UNSET
    vendor: CreateChangeEventResponse201ChangeItemsItemCostImpactVendor | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_change_event_response_201_change_items_item_cost_impact_change_order_package_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_commitment_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_request_for_quote_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0,
        )

        change_order_package: dict[str, Any] | None | Unset
        if isinstance(self.change_order_package, Unset):
            change_order_package = UNSET
        elif isinstance(
            self.change_order_package,
            CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0,
        ):
            change_order_package = self.change_order_package.to_dict()
        else:
            change_order_package = self.change_order_package

        commitment: dict[str, Any] | None | Unset
        if isinstance(self.commitment, Unset):
            commitment = UNSET
        elif isinstance(
            self.commitment,
            CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0,
        ):
            commitment = self.commitment.to_dict()
        else:
            commitment = self.commitment

        contract: dict[str, Any] | Unset = UNSET
        if not isinstance(self.contract, Unset):
            contract = self.contract.to_dict()

        estimate: dict[str, Any] | Unset = UNSET
        if not isinstance(self.estimate, Unset):
            estimate = self.estimate.to_dict()

        non_commitment: dict[str, Any] | Unset = UNSET
        if not isinstance(self.non_commitment, Unset):
            non_commitment = self.non_commitment.to_dict()

        request_for_quote: dict[str, Any] | None | Unset
        if isinstance(self.request_for_quote, Unset):
            request_for_quote = UNSET
        elif isinstance(
            self.request_for_quote,
            CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0,
        ):
            request_for_quote = self.request_for_quote.to_dict()
        else:
            request_for_quote = self.request_for_quote

        source_of_latest_cost: str | Unset = UNSET
        if not isinstance(self.source_of_latest_cost, Unset):
            source_of_latest_cost = self.source_of_latest_cost.value

        source_of_stage: str | Unset = UNSET
        if not isinstance(self.source_of_stage, Unset):
            source_of_stage = self.source_of_stage.value

        vendor: dict[str, Any] | Unset = UNSET
        if not isinstance(self.vendor, Unset):
            vendor = self.vendor.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if change_order_package is not UNSET:
            field_dict["change_order_package"] = change_order_package
        if commitment is not UNSET:
            field_dict["commitment"] = commitment
        if contract is not UNSET:
            field_dict["contract"] = contract
        if estimate is not UNSET:
            field_dict["estimate"] = estimate
        if non_commitment is not UNSET:
            field_dict["non_commitment"] = non_commitment
        if request_for_quote is not UNSET:
            field_dict["request_for_quote"] = request_for_quote
        if source_of_latest_cost is not UNSET:
            field_dict["source_of_latest_cost"] = source_of_latest_cost
        if source_of_stage is not UNSET:
            field_dict["source_of_stage"] = source_of_stage
        if vendor is not UNSET:
            field_dict["vendor"] = vendor

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_response_201_change_items_item_cost_impact_change_order_package_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_commitment_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_contract import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactContract,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_estimate import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_non_commitment import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactNonCommitment,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_request_for_quote_type_0 import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0,
        )
        from ..models.create_change_event_response_201_change_items_item_cost_impact_vendor import (
            CreateChangeEventResponse201ChangeItemsItemCostImpactVendor,
        )

        d = dict(src_dict)

        def _parse_change_order_package(
            data: object,
        ) -> (
            CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                change_order_package_type_0 = CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0.from_dict(
                    data
                )

                return change_order_package_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventResponse201ChangeItemsItemCostImpactChangeOrderPackageType0
                | None
                | Unset,
                data,
            )

        change_order_package = _parse_change_order_package(
            d.pop("change_order_package", UNSET)
        )

        def _parse_commitment(
            data: object,
        ) -> (
            CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                commitment_type_0 = CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0.from_dict(
                    data
                )

                return commitment_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventResponse201ChangeItemsItemCostImpactCommitmentType0
                | None
                | Unset,
                data,
            )

        commitment = _parse_commitment(d.pop("commitment", UNSET))

        _contract = d.pop("contract", UNSET)
        contract: CreateChangeEventResponse201ChangeItemsItemCostImpactContract | Unset
        if isinstance(_contract, Unset):
            contract = UNSET
        else:
            contract = (
                CreateChangeEventResponse201ChangeItemsItemCostImpactContract.from_dict(
                    _contract
                )
            )

        _estimate = d.pop("estimate", UNSET)
        estimate: CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate | Unset
        if isinstance(_estimate, Unset):
            estimate = UNSET
        else:
            estimate = (
                CreateChangeEventResponse201ChangeItemsItemCostImpactEstimate.from_dict(
                    _estimate
                )
            )

        _non_commitment = d.pop("non_commitment", UNSET)
        non_commitment: (
            CreateChangeEventResponse201ChangeItemsItemCostImpactNonCommitment | Unset
        )
        if isinstance(_non_commitment, Unset):
            non_commitment = UNSET
        else:
            non_commitment = CreateChangeEventResponse201ChangeItemsItemCostImpactNonCommitment.from_dict(
                _non_commitment
            )

        def _parse_request_for_quote(
            data: object,
        ) -> (
            CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                request_for_quote_type_0 = CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0.from_dict(
                    data
                )

                return request_for_quote_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateChangeEventResponse201ChangeItemsItemCostImpactRequestForQuoteType0
                | None
                | Unset,
                data,
            )

        request_for_quote = _parse_request_for_quote(d.pop("request_for_quote", UNSET))

        _source_of_latest_cost = d.pop("source_of_latest_cost", UNSET)
        source_of_latest_cost: (
            CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfLatestCost
            | Unset
        )
        if isinstance(_source_of_latest_cost, Unset):
            source_of_latest_cost = UNSET
        else:
            source_of_latest_cost = (
                CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfLatestCost(
                    _source_of_latest_cost
                )
            )

        _source_of_stage = d.pop("source_of_stage", UNSET)
        source_of_stage: (
            CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfStage | Unset
        )
        if isinstance(_source_of_stage, Unset):
            source_of_stage = UNSET
        else:
            source_of_stage = (
                CreateChangeEventResponse201ChangeItemsItemCostImpactSourceOfStage(
                    _source_of_stage
                )
            )

        _vendor = d.pop("vendor", UNSET)
        vendor: CreateChangeEventResponse201ChangeItemsItemCostImpactVendor | Unset
        if isinstance(_vendor, Unset):
            vendor = UNSET
        else:
            vendor = (
                CreateChangeEventResponse201ChangeItemsItemCostImpactVendor.from_dict(
                    _vendor
                )
            )

        create_change_event_response_201_change_items_item_cost_impact = cls(
            change_order_package=change_order_package,
            commitment=commitment,
            contract=contract,
            estimate=estimate,
            non_commitment=non_commitment,
            request_for_quote=request_for_quote,
            source_of_latest_cost=source_of_latest_cost,
            source_of_stage=source_of_stage,
            vendor=vendor,
        )

        create_change_event_response_201_change_items_item_cost_impact.additional_properties = d
        return create_change_event_response_201_change_items_item_cost_impact

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
