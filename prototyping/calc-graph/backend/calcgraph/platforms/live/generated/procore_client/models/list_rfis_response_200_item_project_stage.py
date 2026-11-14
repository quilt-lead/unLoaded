from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListRfisResponse200ItemProjectStage")


@_attrs_define
class ListRfisResponse200ItemProjectStage:
    """
    Attributes:
        default_stage (bool | Unset): Default Stage
        dependent_projects (int | Unset): Dependent Projects count
        formatted_name (str | Unset): Formatted Name
        formatted_parent_name (str | Unset): Formatted Parent Name
        id (int | Unset): ID
        name (str | Unset): Name
        parent_id (int | Unset): Construction Volume Stage ID. Returns null if prefix is linked to a project stage that
            is the parent.
        procore_category (bool | Unset): Indicates whether the project stage the prefix is linked to is a Construction
            Volume default stage.
    """

    default_stage: bool | Unset = UNSET
    dependent_projects: int | Unset = UNSET
    formatted_name: str | Unset = UNSET
    formatted_parent_name: str | Unset = UNSET
    id: int | Unset = UNSET
    name: str | Unset = UNSET
    parent_id: int | Unset = UNSET
    procore_category: bool | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        default_stage = self.default_stage

        dependent_projects = self.dependent_projects

        formatted_name = self.formatted_name

        formatted_parent_name = self.formatted_parent_name

        id = self.id

        name = self.name

        parent_id = self.parent_id

        procore_category = self.procore_category

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if default_stage is not UNSET:
            field_dict["default_stage"] = default_stage
        if dependent_projects is not UNSET:
            field_dict["dependent_projects"] = dependent_projects
        if formatted_name is not UNSET:
            field_dict["formatted_name"] = formatted_name
        if formatted_parent_name is not UNSET:
            field_dict["formatted_parent_name"] = formatted_parent_name
        if id is not UNSET:
            field_dict["id"] = id
        if name is not UNSET:
            field_dict["name"] = name
        if parent_id is not UNSET:
            field_dict["parent_id"] = parent_id
        if procore_category is not UNSET:
            field_dict["procore_category"] = procore_category

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        default_stage = d.pop("default_stage", UNSET)

        dependent_projects = d.pop("dependent_projects", UNSET)

        formatted_name = d.pop("formatted_name", UNSET)

        formatted_parent_name = d.pop("formatted_parent_name", UNSET)

        id = d.pop("id", UNSET)

        name = d.pop("name", UNSET)

        parent_id = d.pop("parent_id", UNSET)

        procore_category = d.pop("procore_category", UNSET)

        list_rfis_response_200_item_project_stage = cls(
            default_stage=default_stage,
            dependent_projects=dependent_projects,
            formatted_name=formatted_name,
            formatted_parent_name=formatted_parent_name,
            id=id,
            name=name,
            parent_id=parent_id,
            procore_category=procore_category,
        )

        list_rfis_response_200_item_project_stage.additional_properties = d
        return list_rfis_response_200_item_project_stage

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
