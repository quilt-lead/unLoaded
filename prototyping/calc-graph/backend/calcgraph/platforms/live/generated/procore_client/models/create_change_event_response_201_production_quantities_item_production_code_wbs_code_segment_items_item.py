from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_production_quantities_item_production_code_wbs_code_segment_items_item_status import (
    CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_change_event_response_201_production_quantities_item_production_code_wbs_code_segment_items_item_segment import (
        CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegment,
    )


T = TypeVar(
    "T",
    bound="CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItem",
)


@_attrs_define
class CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItem:
    """
    Attributes:
        code (str | Unset): Short alphanumeric code for this segment item (e.g., '01-222'). Combined with sibling
            segment codes to form the flat_code on the parent WBS code.
        created_at (datetime.datetime | Unset): Timestamp when this segment item was created, in ISO 8601 format.
        id (int | Unset): Unique ID of this segment item (cost code, sub-job, line item type, or custom segment item).
            Use as segment_item_id when constructing a new WBS code via POST
            /rest/v1.0/projects/{project_id}/work_breakdown_structure/wbs_codes.
        in_use (bool | Unset): Whether this segment item is currently referenced by at least one entity (e.g., a budget
            line item or WBS code).
        is_parent (bool | Unset): Whether this segment item has child items in a tiered segment structure. Always false
            for flat-structure segments.
        name (str | Unset): Human-readable name of this segment item (e.g., 'Lighting'). Combined with sibling segment
            names to form the flat_name on the parent WBS code.
        parent_id (int | None | Unset): ID of the parent segment item in a tiered segment hierarchy. Null for root-level
            items or items in a flat-structure segment.
        path_code (str | Unset): Full path code for this segment item representing the leaf code in its hierarchy (e.g.,
            '01-222').
        path_codes (list[str] | Unset): Ordered list of code strings from the root ancestor down to (and including) this
            segment item, formatted as 'code - name'.
        path_ids (list[int] | Unset): Ordered list of IDs from the root ancestor down to (and including) this segment
            item. Use to reconstruct the full hierarchy path.
        path_names (list[str] | Unset): Ordered list of name strings from the root ancestor down to (and including) this
            segment item, formatted as 'code - name'.
        segment (CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegment |
            Unset): The WBS segment definition that this segment item belongs to.
        status (CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus |
            Unset): Lifecycle status of the segment item. One of: 'active' (available for selection when creating WBS
            codes), 'inactive' (not available for new WBS codes).
        updated_at (datetime.datetime | Unset): Timestamp when this segment item was last updated, in ISO 8601 format.
    """

    code: str | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    id: int | Unset = UNSET
    in_use: bool | Unset = UNSET
    is_parent: bool | Unset = UNSET
    name: str | Unset = UNSET
    parent_id: int | None | Unset = UNSET
    path_code: str | Unset = UNSET
    path_codes: list[str] | Unset = UNSET
    path_ids: list[int] | Unset = UNSET
    path_names: list[str] | Unset = UNSET
    segment: (
        CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegment
        | Unset
    ) = UNSET
    status: (
        CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus
        | Unset
    ) = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        code = self.code

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        id = self.id

        in_use = self.in_use

        is_parent = self.is_parent

        name = self.name

        parent_id: int | None | Unset
        if isinstance(self.parent_id, Unset):
            parent_id = UNSET
        else:
            parent_id = self.parent_id

        path_code = self.path_code

        path_codes: list[str] | Unset = UNSET
        if not isinstance(self.path_codes, Unset):
            path_codes = self.path_codes

        path_ids: list[int] | Unset = UNSET
        if not isinstance(self.path_ids, Unset):
            path_ids = self.path_ids

        path_names: list[str] | Unset = UNSET
        if not isinstance(self.path_names, Unset):
            path_names = self.path_names

        segment: dict[str, Any] | Unset = UNSET
        if not isinstance(self.segment, Unset):
            segment = self.segment.to_dict()

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if code is not UNSET:
            field_dict["code"] = code
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if id is not UNSET:
            field_dict["id"] = id
        if in_use is not UNSET:
            field_dict["in_use"] = in_use
        if is_parent is not UNSET:
            field_dict["is_parent"] = is_parent
        if name is not UNSET:
            field_dict["name"] = name
        if parent_id is not UNSET:
            field_dict["parent_id"] = parent_id
        if path_code is not UNSET:
            field_dict["path_code"] = path_code
        if path_codes is not UNSET:
            field_dict["path_codes"] = path_codes
        if path_ids is not UNSET:
            field_dict["path_ids"] = path_ids
        if path_names is not UNSET:
            field_dict["path_names"] = path_names
        if segment is not UNSET:
            field_dict["segment"] = segment
        if status is not UNSET:
            field_dict["status"] = status
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_change_event_response_201_production_quantities_item_production_code_wbs_code_segment_items_item_segment import (
            CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegment,
        )

        d = dict(src_dict)
        code = d.pop("code", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        id = d.pop("id", UNSET)

        in_use = d.pop("in_use", UNSET)

        is_parent = d.pop("is_parent", UNSET)

        name = d.pop("name", UNSET)

        def _parse_parent_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        parent_id = _parse_parent_id(d.pop("parent_id", UNSET))

        path_code = d.pop("path_code", UNSET)

        path_codes = cast(list[str], d.pop("path_codes", UNSET))

        path_ids = cast(list[int], d.pop("path_ids", UNSET))

        path_names = cast(list[str], d.pop("path_names", UNSET))

        _segment = d.pop("segment", UNSET)
        segment: (
            CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegment
            | Unset
        )
        if isinstance(_segment, Unset):
            segment = UNSET
        else:
            segment = CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemSegment.from_dict(
                _segment
            )

        _status = d.pop("status", UNSET)
        status: (
            CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus
            | Unset
        )
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = CreateChangeEventResponse201ProductionQuantitiesItemProductionCodeWbsCodeSegmentItemsItemStatus(
                _status
            )

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        create_change_event_response_201_production_quantities_item_production_code_wbs_code_segment_items_item = cls(
            code=code,
            created_at=created_at,
            id=id,
            in_use=in_use,
            is_parent=is_parent,
            name=name,
            parent_id=parent_id,
            path_code=path_code,
            path_codes=path_codes,
            path_ids=path_ids,
            path_names=path_names,
            segment=segment,
            status=status,
            updated_at=updated_at,
        )

        create_change_event_response_201_production_quantities_item_production_code_wbs_code_segment_items_item.additional_properties = d
        return create_change_event_response_201_production_quantities_item_production_code_wbs_code_segment_items_item

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
