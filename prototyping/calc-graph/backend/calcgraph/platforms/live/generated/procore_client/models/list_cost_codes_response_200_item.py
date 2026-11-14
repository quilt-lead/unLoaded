from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_cost_codes_response_200_item_biller_type import (
    ListCostCodesResponse200ItemBillerType,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_cost_codes_response_200_item_line_item_types_item import (
        ListCostCodesResponse200ItemLineItemTypesItem,
    )
    from ..models.list_cost_codes_response_200_item_parent import (
        ListCostCodesResponse200ItemParent,
    )


T = TypeVar("T", bound="ListCostCodesResponse200Item")


@_attrs_define
class ListCostCodesResponse200Item:
    """
    Attributes:
        biller (str | Unset): Display name of the entity (project or sub job) that owns this cost code.
        biller_id (int | None | Unset): Procore ID of the owning project or sub job. Use with biller_type to identify
            the owning entity.
        biller_origin_id (None | str | Unset): ERP origin ID of the owning project or sub job. Null when no ERP origin
            has been set.
        biller_type (ListCostCodesResponse200ItemBillerType | Unset): Type of entity that owns this cost code. One of:
            'Project' (a standard project), 'SubJob' (a sub job within the project), or '' (empty string when unassigned).
        budgeted (bool | Unset): Whether this cost code has been marked as budgeted. True when at least one budget line
            item exists for this cost code.
        code (None | str | Unset): Cost code segment, not including the parent prefix. For example, for full code
            "02-300", this field is "300".
        created_at (datetime.datetime | None | Unset): Timestamp when this cost code was created, in ISO 8601 format.
        deleted_at (datetime.datetime | None | Unset): Timestamp when this cost code was soft-deleted, in ISO 8601
            format. Null when the record is active.
        full_code (str | Unset): Full cost code including all parent prefixes (e.g. "02-300").
        id (int | None | Unset): Unique identifier for this Cost Code record. Nullable when the record has not yet been
            persisted.
        line_item_types (list[ListCostCodesResponse200ItemLineItemTypesItem] | Unset): Array of line item types (cost
            types) assigned to this cost code. Each entry represents one Cost Code / Line Item Type assignment.
        name (str | Unset): Display name of the cost code.
        origin_data (None | str | Unset): Free-form third-party metadata string from the ERP system. Null when no ERP
            origin data has been set.
        origin_id (None | str | Unset): ERP system identifier for this cost code. Used by sync operations to match
            records across systems. Null when not linked to an ERP system.
        parent (ListCostCodesResponse200ItemParent | Unset): The immediate parent cost code of this record, if any.
        position (int | None | Unset): Sort order of this cost code within its parent.
        sortable_code (str | Unset): Deprecated alias for full_code. Use full_code instead. Included for backwards
            compatibility.
        standard_cost_code_id (int | None | Unset): ID of the company-level standard cost code that this project cost
            code was created from. Null when not derived from a standard list.
        updated_at (datetime.datetime | None | Unset): Timestamp when this cost code was last updated, in ISO 8601
            format. Null when not available.
    """

    biller: str | Unset = UNSET
    biller_id: int | None | Unset = UNSET
    biller_origin_id: None | str | Unset = UNSET
    biller_type: ListCostCodesResponse200ItemBillerType | Unset = UNSET
    budgeted: bool | Unset = UNSET
    code: None | str | Unset = UNSET
    created_at: datetime.datetime | None | Unset = UNSET
    deleted_at: datetime.datetime | None | Unset = UNSET
    full_code: str | Unset = UNSET
    id: int | None | Unset = UNSET
    line_item_types: list[ListCostCodesResponse200ItemLineItemTypesItem] | Unset = UNSET
    name: str | Unset = UNSET
    origin_data: None | str | Unset = UNSET
    origin_id: None | str | Unset = UNSET
    parent: ListCostCodesResponse200ItemParent | Unset = UNSET
    position: int | None | Unset = UNSET
    sortable_code: str | Unset = UNSET
    standard_cost_code_id: int | None | Unset = UNSET
    updated_at: datetime.datetime | None | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        biller = self.biller

        biller_id: int | None | Unset
        if isinstance(self.biller_id, Unset):
            biller_id = UNSET
        else:
            biller_id = self.biller_id

        biller_origin_id: None | str | Unset
        if isinstance(self.biller_origin_id, Unset):
            biller_origin_id = UNSET
        else:
            biller_origin_id = self.biller_origin_id

        biller_type: str | Unset = UNSET
        if not isinstance(self.biller_type, Unset):
            biller_type = self.biller_type.value

        budgeted = self.budgeted

        code: None | str | Unset
        if isinstance(self.code, Unset):
            code = UNSET
        else:
            code = self.code

        created_at: None | str | Unset
        if isinstance(self.created_at, Unset):
            created_at = UNSET
        elif isinstance(self.created_at, datetime.datetime):
            created_at = self.created_at.isoformat()
        else:
            created_at = self.created_at

        deleted_at: None | str | Unset
        if isinstance(self.deleted_at, Unset):
            deleted_at = UNSET
        elif isinstance(self.deleted_at, datetime.datetime):
            deleted_at = self.deleted_at.isoformat()
        else:
            deleted_at = self.deleted_at

        full_code = self.full_code

        id: int | None | Unset
        if isinstance(self.id, Unset):
            id = UNSET
        else:
            id = self.id

        line_item_types: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.line_item_types, Unset):
            line_item_types = []
            for line_item_types_item_data in self.line_item_types:
                line_item_types_item = line_item_types_item_data.to_dict()
                line_item_types.append(line_item_types_item)

        name = self.name

        origin_data: None | str | Unset
        if isinstance(self.origin_data, Unset):
            origin_data = UNSET
        else:
            origin_data = self.origin_data

        origin_id: None | str | Unset
        if isinstance(self.origin_id, Unset):
            origin_id = UNSET
        else:
            origin_id = self.origin_id

        parent: dict[str, Any] | Unset = UNSET
        if not isinstance(self.parent, Unset):
            parent = self.parent.to_dict()

        position: int | None | Unset
        if isinstance(self.position, Unset):
            position = UNSET
        else:
            position = self.position

        sortable_code = self.sortable_code

        standard_cost_code_id: int | None | Unset
        if isinstance(self.standard_cost_code_id, Unset):
            standard_cost_code_id = UNSET
        else:
            standard_cost_code_id = self.standard_cost_code_id

        updated_at: None | str | Unset
        if isinstance(self.updated_at, Unset):
            updated_at = UNSET
        elif isinstance(self.updated_at, datetime.datetime):
            updated_at = self.updated_at.isoformat()
        else:
            updated_at = self.updated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if biller is not UNSET:
            field_dict["biller"] = biller
        if biller_id is not UNSET:
            field_dict["biller_id"] = biller_id
        if biller_origin_id is not UNSET:
            field_dict["biller_origin_id"] = biller_origin_id
        if biller_type is not UNSET:
            field_dict["biller_type"] = biller_type
        if budgeted is not UNSET:
            field_dict["budgeted"] = budgeted
        if code is not UNSET:
            field_dict["code"] = code
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if full_code is not UNSET:
            field_dict["full_code"] = full_code
        if id is not UNSET:
            field_dict["id"] = id
        if line_item_types is not UNSET:
            field_dict["line_item_types"] = line_item_types
        if name is not UNSET:
            field_dict["name"] = name
        if origin_data is not UNSET:
            field_dict["origin_data"] = origin_data
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id
        if parent is not UNSET:
            field_dict["parent"] = parent
        if position is not UNSET:
            field_dict["position"] = position
        if sortable_code is not UNSET:
            field_dict["sortable_code"] = sortable_code
        if standard_cost_code_id is not UNSET:
            field_dict["standard_cost_code_id"] = standard_cost_code_id
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_cost_codes_response_200_item_line_item_types_item import (
            ListCostCodesResponse200ItemLineItemTypesItem,
        )
        from ..models.list_cost_codes_response_200_item_parent import (
            ListCostCodesResponse200ItemParent,
        )

        d = dict(src_dict)
        biller = d.pop("biller", UNSET)

        def _parse_biller_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        biller_id = _parse_biller_id(d.pop("biller_id", UNSET))

        def _parse_biller_origin_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        biller_origin_id = _parse_biller_origin_id(d.pop("biller_origin_id", UNSET))

        _biller_type = d.pop("biller_type", UNSET)
        biller_type: ListCostCodesResponse200ItemBillerType | Unset
        if isinstance(_biller_type, Unset):
            biller_type = UNSET
        else:
            biller_type = ListCostCodesResponse200ItemBillerType(_biller_type)

        budgeted = d.pop("budgeted", UNSET)

        def _parse_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        code = _parse_code(d.pop("code", UNSET))

        def _parse_created_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                created_at_type_0 = datetime.datetime.fromisoformat(data)

                return created_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        created_at = _parse_created_at(d.pop("created_at", UNSET))

        def _parse_deleted_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                deleted_at_type_0 = datetime.datetime.fromisoformat(data)

                return deleted_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        deleted_at = _parse_deleted_at(d.pop("deleted_at", UNSET))

        full_code = d.pop("full_code", UNSET)

        def _parse_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        id = _parse_id(d.pop("id", UNSET))

        _line_item_types = d.pop("line_item_types", UNSET)
        line_item_types: list[ListCostCodesResponse200ItemLineItemTypesItem] | Unset = (
            UNSET
        )
        if _line_item_types is not UNSET:
            line_item_types = []
            for line_item_types_item_data in _line_item_types:
                line_item_types_item = (
                    ListCostCodesResponse200ItemLineItemTypesItem.from_dict(
                        line_item_types_item_data
                    )
                )

                line_item_types.append(line_item_types_item)

        name = d.pop("name", UNSET)

        def _parse_origin_data(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_data = _parse_origin_data(d.pop("origin_data", UNSET))

        def _parse_origin_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_id = _parse_origin_id(d.pop("origin_id", UNSET))

        _parent = d.pop("parent", UNSET)
        parent: ListCostCodesResponse200ItemParent | Unset
        if isinstance(_parent, Unset):
            parent = UNSET
        else:
            parent = ListCostCodesResponse200ItemParent.from_dict(_parent)

        def _parse_position(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        position = _parse_position(d.pop("position", UNSET))

        sortable_code = d.pop("sortable_code", UNSET)

        def _parse_standard_cost_code_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        standard_cost_code_id = _parse_standard_cost_code_id(
            d.pop("standard_cost_code_id", UNSET)
        )

        def _parse_updated_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                updated_at_type_0 = datetime.datetime.fromisoformat(data)

                return updated_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        updated_at = _parse_updated_at(d.pop("updated_at", UNSET))

        list_cost_codes_response_200_item = cls(
            biller=biller,
            biller_id=biller_id,
            biller_origin_id=biller_origin_id,
            biller_type=biller_type,
            budgeted=budgeted,
            code=code,
            created_at=created_at,
            deleted_at=deleted_at,
            full_code=full_code,
            id=id,
            line_item_types=line_item_types,
            name=name,
            origin_data=origin_data,
            origin_id=origin_id,
            parent=parent,
            position=position,
            sortable_code=sortable_code,
            standard_cost_code_id=standard_cost_code_id,
            updated_at=updated_at,
        )

        list_cost_codes_response_200_item.additional_properties = d
        return list_cost_codes_response_200_item

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
