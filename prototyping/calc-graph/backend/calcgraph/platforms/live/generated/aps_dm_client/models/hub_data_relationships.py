from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.hub_data_relationships_pim_collection import (
        HubDataRelationshipsPimCollection,
    )
    from ..models.hub_data_relationships_projects import HubDataRelationshipsProjects


T = TypeVar("T", bound="HubDataRelationships")


@_attrs_define
class HubDataRelationships:
    """Contains links to resources that are directly related to this hub.

    Attributes:
        pim_collection (HubDataRelationshipsPimCollection | Unset): Information on the ``id`` and ``type`` properties of
            a resource. This is available only for Fusion Team hubs and A360 Personal hubs.
        projects (HubDataRelationshipsProjects | Unset): Contains the endpoint you can use to
            list the projects in this hub.
    """

    pim_collection: HubDataRelationshipsPimCollection | Unset = UNSET
    projects: HubDataRelationshipsProjects | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        pim_collection: dict[str, Any] | Unset = UNSET
        if not isinstance(self.pim_collection, Unset):
            pim_collection = self.pim_collection.to_dict()

        projects: dict[str, Any] | Unset = UNSET
        if not isinstance(self.projects, Unset):
            projects = self.projects.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if pim_collection is not UNSET:
            field_dict["pimCollection"] = pim_collection
        if projects is not UNSET:
            field_dict["projects"] = projects

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.hub_data_relationships_pim_collection import (
            HubDataRelationshipsPimCollection,
        )
        from ..models.hub_data_relationships_projects import (
            HubDataRelationshipsProjects,
        )

        d = dict(src_dict)
        _pim_collection = d.pop("pimCollection", UNSET)
        pim_collection: HubDataRelationshipsPimCollection | Unset
        if isinstance(_pim_collection, Unset):
            pim_collection = UNSET
        else:
            pim_collection = HubDataRelationshipsPimCollection.from_dict(
                _pim_collection
            )

        _projects = d.pop("projects", UNSET)
        projects: HubDataRelationshipsProjects | Unset
        if isinstance(_projects, Unset):
            projects = UNSET
        else:
            projects = HubDataRelationshipsProjects.from_dict(_projects)

        hub_data_relationships = cls(
            pim_collection=pim_collection,
            projects=projects,
        )

        hub_data_relationships.additional_properties = d
        return hub_data_relationships

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
