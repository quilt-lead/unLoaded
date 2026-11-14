from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_change_event_response_201_markup_items_item_wbs_code_segment_items_item_segment_structure import (
    CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentStructure,
)
from ..models.create_change_event_response_201_markup_items_item_wbs_code_segment_items_item_segment_type import (
    CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentType,
)
from ..types import UNSET, Unset

T = TypeVar(
    "T",
    bound="CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegment",
)


@_attrs_define
class CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegment:
    """The WBS segment definition that this segment item belongs to.

    Attributes:
        created_at (datetime.datetime | Unset): Timestamp when this segment definition was created, in ISO 8601 format.
        delimiter (str | Unset): Character used to separate this segment's value from adjacent segments in the flat_code
            (e.g., '.').
        id (int | Unset): Unique ID of the WBS segment definition.
        name (str | Unset): Display name of the segment (e.g., 'Cost Code', 'Sub Job').
        position (int | Unset): Display order of this segment within the WBS pattern. Lower numbers appear first when
            reading the flat_code left to right.
        project_can_delete_origin_company (bool | Unset): Whether project-level users can delete segment items that
            originated from the company level.
        project_can_modify_origin_project (bool | Unset): Whether project-level users can modify segment items that
            originated from this project.
        required (bool | Unset): Whether this segment must have a value for a WBS code to be valid.
        segment_items_count (int | Unset): Total number of segment items defined for this segment.
        structure (CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentStructure | Unset):
            Hierarchy structure of the segment. 'flat' means items have no parent-child relationship; 'tiered' means items
            can be nested with parent_id references.
        type_ (CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentType | Unset): Category of this
            segment. One of: 'cost_code', 'line_item_type', 'sub_job', 'custom', 'attribute'. Determines which domain entity
            backs the segment items.
        updated_at (datetime.datetime | Unset): Timestamp when this segment definition was last updated, in ISO 8601
            format.
        wbs_pattern_id (int | Unset): ID of the WBS pattern this segment belongs to.
    """

    created_at: datetime.datetime | Unset = UNSET
    delimiter: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    position: int | Unset = UNSET
    project_can_delete_origin_company: bool | Unset = UNSET
    project_can_modify_origin_project: bool | Unset = UNSET
    required: bool | Unset = UNSET
    segment_items_count: int | Unset = UNSET
    structure: (
        CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentStructure
        | Unset
    ) = UNSET
    type_: (
        CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentType
        | Unset
    ) = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    wbs_pattern_id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        delimiter = self.delimiter

        id = self.id

        name = self.name

        position = self.position

        project_can_delete_origin_company = self.project_can_delete_origin_company

        project_can_modify_origin_project = self.project_can_modify_origin_project

        required = self.required

        segment_items_count = self.segment_items_count

        structure: str | Unset = UNSET
        if not isinstance(self.structure, Unset):
            structure = self.structure.value

        type_: str | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.value

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        wbs_pattern_id = self.wbs_pattern_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if delimiter is not UNSET:
            field_dict["delimiter"] = delimiter
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if position is not UNSET:
            field_dict["position"] = position
        if project_can_delete_origin_company is not UNSET:
            field_dict["project_can_delete_origin_company"] = (
                project_can_delete_origin_company
            )
        if project_can_modify_origin_project is not UNSET:
            field_dict["project_can_modify_origin_project"] = (
                project_can_modify_origin_project
            )
        if required is not UNSET:
            field_dict["required"] = required
        if segment_items_count is not UNSET:
            field_dict["segment_items_count"] = segment_items_count
        if structure is not UNSET:
            field_dict["structure"] = structure
        if type_ is not UNSET:
            field_dict["type"] = type_
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at
        if wbs_pattern_id is not UNSET:
            field_dict["wbs_pattern_id"] = wbs_pattern_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        delimiter = d.pop("delimiter", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        position = d.pop("position", UNSET)

        project_can_delete_origin_company = d.pop(
            "project_can_delete_origin_company", UNSET
        )

        project_can_modify_origin_project = d.pop(
            "project_can_modify_origin_project", UNSET
        )

        required = d.pop("required", UNSET)

        segment_items_count = d.pop("segment_items_count", UNSET)

        _structure = d.pop("structure", UNSET)
        structure: (
            CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentStructure
            | Unset
        )
        if isinstance(_structure, Unset):
            structure = UNSET
        else:
            structure = CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentStructure(
                _structure
            )

        _type_ = d.pop("type", UNSET)
        type_: (
            CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentType
            | Unset
        )
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = CreateChangeEventResponse201MarkupItemsItemWbsCodeSegmentItemsItemSegmentType(
                _type_
            )

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        wbs_pattern_id = d.pop("wbs_pattern_id", UNSET)

        create_change_event_response_201_markup_items_item_wbs_code_segment_items_item_segment = cls(
            created_at=created_at,
            delimiter=delimiter,
            id=id,
            name=name,
            position=position,
            project_can_delete_origin_company=project_can_delete_origin_company,
            project_can_modify_origin_project=project_can_modify_origin_project,
            required=required,
            segment_items_count=segment_items_count,
            structure=structure,
            type_=type_,
            updated_at=updated_at,
            wbs_pattern_id=wbs_pattern_id,
        )

        create_change_event_response_201_markup_items_item_wbs_code_segment_items_item_segment.additional_properties = d
        return create_change_event_response_201_markup_items_item_wbs_code_segment_items_item_segment

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
