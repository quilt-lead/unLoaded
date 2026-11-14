from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_cost_code import (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode,
    )
    from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_sub_job import (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob,
    )
    from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_line_item_type import (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType,
    )


T = TypeVar(
    "T", bound="ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup"
)


@_attrs_define
class ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkup:
    """
    Attributes:
        compounds_markups_above (bool | Unset): Compounds markups above?
        created_at (datetime.datetime | Unset): Created at
        desitination_budget_line_item_id (int | Unset): Destination Budget Line Item ID
        destination_cost_code (ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode |
            Unset):
        destination_line_item_type (ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType |
            Unset): Line Item Type
        destination_sub_job (ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob | Unset):
        id (int | Unset): Markup ID
        markup_set (str | Unset): Markup set
        name (str | Unset): name
        percentage (str | Unset): Percentage
        position (int | Unset): Position
        updated_at (datetime.datetime | Unset): Updated at
        wbs_code_id (int | Unset): Work Breakdown Structure Code ID
    """

    compounds_markups_above: bool | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    desitination_budget_line_item_id: int | Unset = UNSET
    destination_cost_code: (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode
        | Unset
    ) = UNSET
    destination_line_item_type: (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType
        | Unset
    ) = UNSET
    destination_sub_job: (
        ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob
        | Unset
    ) = UNSET
    id: int | Unset = UNSET
    markup_set: str | Unset = UNSET
    name: str | Unset = UNSET
    percentage: str | Unset = UNSET
    position: int | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    wbs_code_id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        compounds_markups_above = self.compounds_markups_above

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        desitination_budget_line_item_id = self.desitination_budget_line_item_id

        destination_cost_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.destination_cost_code, Unset):
            destination_cost_code = self.destination_cost_code.to_dict()

        destination_line_item_type: dict[str, Any] | Unset = UNSET
        if not isinstance(self.destination_line_item_type, Unset):
            destination_line_item_type = self.destination_line_item_type.to_dict()

        destination_sub_job: dict[str, Any] | Unset = UNSET
        if not isinstance(self.destination_sub_job, Unset):
            destination_sub_job = self.destination_sub_job.to_dict()

        id = self.id

        markup_set = self.markup_set

        name = self.name

        percentage = self.percentage

        position = self.position

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        wbs_code_id = self.wbs_code_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if compounds_markups_above is not UNSET:
            field_dict["compounds_markups_above"] = compounds_markups_above
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if desitination_budget_line_item_id is not UNSET:
            field_dict["desitination_budget_line_item_id"] = (
                desitination_budget_line_item_id
            )
        if destination_cost_code is not UNSET:
            field_dict["destination_cost_code"] = destination_cost_code
        if destination_line_item_type is not UNSET:
            field_dict["destination_line_item_type"] = destination_line_item_type
        if destination_sub_job is not UNSET:
            field_dict["destination_sub_job"] = destination_sub_job
        if id is not UNSET:
            field_dict["id"] = id
        if markup_set is not UNSET:
            field_dict["markup_set"] = markup_set
        if name is not UNSET:
            field_dict["name"] = name
        if percentage is not UNSET:
            field_dict["percentage"] = percentage
        if position is not UNSET:
            field_dict["position"] = position
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at
        if wbs_code_id is not UNSET:
            field_dict["wbs_code_id"] = wbs_code_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_cost_code import (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode,
        )
        from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_destination_sub_job import (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob,
        )
        from ..models.procore_change_order_package_line_items_item_markup_line_items_item_markup_line_item_type import (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType,
        )

        d = dict(src_dict)
        compounds_markups_above = d.pop("compounds_markups_above", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        desitination_budget_line_item_id = d.pop(
            "desitination_budget_line_item_id", UNSET
        )

        _destination_cost_code = d.pop("destination_cost_code", UNSET)
        destination_cost_code: (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode
            | Unset
        )
        if isinstance(_destination_cost_code, Unset):
            destination_cost_code = UNSET
        else:
            destination_cost_code = ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationCostCode.from_dict(
                _destination_cost_code
            )

        _destination_line_item_type = d.pop("destination_line_item_type", UNSET)
        destination_line_item_type: (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType
            | Unset
        )
        if isinstance(_destination_line_item_type, Unset):
            destination_line_item_type = UNSET
        else:
            destination_line_item_type = ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupLineItemType.from_dict(
                _destination_line_item_type
            )

        _destination_sub_job = d.pop("destination_sub_job", UNSET)
        destination_sub_job: (
            ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob
            | Unset
        )
        if isinstance(_destination_sub_job, Unset):
            destination_sub_job = UNSET
        else:
            destination_sub_job = ProcoreChangeOrderPackageLineItemsItemMarkupLineItemsItemMarkupDestinationSubJob.from_dict(
                _destination_sub_job
            )

        id = d.pop("id", UNSET)

        markup_set = d.pop("markup_set", UNSET)

        name = d.pop("name", UNSET)

        percentage = d.pop("percentage", UNSET)

        position = d.pop("position", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        wbs_code_id = d.pop("wbs_code_id", UNSET)

        procore_change_order_package_line_items_item_markup_line_items_item_markup = (
            cls(
                compounds_markups_above=compounds_markups_above,
                created_at=created_at,
                desitination_budget_line_item_id=desitination_budget_line_item_id,
                destination_cost_code=destination_cost_code,
                destination_line_item_type=destination_line_item_type,
                destination_sub_job=destination_sub_job,
                id=id,
                markup_set=markup_set,
                name=name,
                percentage=percentage,
                position=position,
                updated_at=updated_at,
                wbs_code_id=wbs_code_id,
            )
        )

        procore_change_order_package_line_items_item_markup_line_items_item_markup.additional_properties = d
        return (
            procore_change_order_package_line_items_item_markup_line_items_item_markup
        )

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
