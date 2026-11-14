from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_relationships_links_internal_resource import (
        JsonApiRelationshipsLinksInternalResource,
    )
    from ..models.json_api_relationships_links_only_bim import (
        JsonApiRelationshipsLinksOnlyBim,
    )
    from ..models.json_api_relationships_links_root_folder import (
        JsonApiRelationshipsLinksRootFolder,
    )
    from ..models.project_data_relationships_top_folders import (
        ProjectDataRelationshipsTopFolders,
    )


T = TypeVar("T", bound="ProjectDataRelationships")


@_attrs_define
class ProjectDataRelationships:
    """Contains links to resources related to this project.

    Attributes:
        checklists (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        cost (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        hub (JsonApiRelationshipsLinksInternalResource | Unset): Information on the resources above this resource in the
            hierarchy.
        issues (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        locations (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        markups (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        rfis (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        root_folder (JsonApiRelationshipsLinksRootFolder | Unset): Information about the root folder of a project.
        submittals (JsonApiRelationshipsLinksOnlyBim | Unset): Contains links to resources that are external to the data
            domain service. This is available only with BIM360.
        top_folders (ProjectDataRelationshipsTopFolders | Unset): Information about the highest level folders you have
            access to.
    """

    checklists: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    cost: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    hub: JsonApiRelationshipsLinksInternalResource | Unset = UNSET
    issues: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    locations: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    markups: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    rfis: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    root_folder: JsonApiRelationshipsLinksRootFolder | Unset = UNSET
    submittals: JsonApiRelationshipsLinksOnlyBim | Unset = UNSET
    top_folders: ProjectDataRelationshipsTopFolders | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        checklists: dict[str, Any] | Unset = UNSET
        if not isinstance(self.checklists, Unset):
            checklists = self.checklists.to_dict()

        cost: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost, Unset):
            cost = self.cost.to_dict()

        hub: dict[str, Any] | Unset = UNSET
        if not isinstance(self.hub, Unset):
            hub = self.hub.to_dict()

        issues: dict[str, Any] | Unset = UNSET
        if not isinstance(self.issues, Unset):
            issues = self.issues.to_dict()

        locations: dict[str, Any] | Unset = UNSET
        if not isinstance(self.locations, Unset):
            locations = self.locations.to_dict()

        markups: dict[str, Any] | Unset = UNSET
        if not isinstance(self.markups, Unset):
            markups = self.markups.to_dict()

        rfis: dict[str, Any] | Unset = UNSET
        if not isinstance(self.rfis, Unset):
            rfis = self.rfis.to_dict()

        root_folder: dict[str, Any] | Unset = UNSET
        if not isinstance(self.root_folder, Unset):
            root_folder = self.root_folder.to_dict()

        submittals: dict[str, Any] | Unset = UNSET
        if not isinstance(self.submittals, Unset):
            submittals = self.submittals.to_dict()

        top_folders: dict[str, Any] | Unset = UNSET
        if not isinstance(self.top_folders, Unset):
            top_folders = self.top_folders.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if checklists is not UNSET:
            field_dict["checklists"] = checklists
        if cost is not UNSET:
            field_dict["cost"] = cost
        if hub is not UNSET:
            field_dict["hub"] = hub
        if issues is not UNSET:
            field_dict["issues"] = issues
        if locations is not UNSET:
            field_dict["locations"] = locations
        if markups is not UNSET:
            field_dict["markups"] = markups
        if rfis is not UNSET:
            field_dict["rfis"] = rfis
        if root_folder is not UNSET:
            field_dict["rootFolder"] = root_folder
        if submittals is not UNSET:
            field_dict["submittals"] = submittals
        if top_folders is not UNSET:
            field_dict["topFolders"] = top_folders

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_relationships_links_internal_resource import (
            JsonApiRelationshipsLinksInternalResource,
        )
        from ..models.json_api_relationships_links_only_bim import (
            JsonApiRelationshipsLinksOnlyBim,
        )
        from ..models.json_api_relationships_links_root_folder import (
            JsonApiRelationshipsLinksRootFolder,
        )
        from ..models.project_data_relationships_top_folders import (
            ProjectDataRelationshipsTopFolders,
        )

        d = dict(src_dict)
        _checklists = d.pop("checklists", UNSET)
        checklists: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_checklists, Unset):
            checklists = UNSET
        else:
            checklists = JsonApiRelationshipsLinksOnlyBim.from_dict(_checklists)

        _cost = d.pop("cost", UNSET)
        cost: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_cost, Unset):
            cost = UNSET
        else:
            cost = JsonApiRelationshipsLinksOnlyBim.from_dict(_cost)

        _hub = d.pop("hub", UNSET)
        hub: JsonApiRelationshipsLinksInternalResource | Unset
        if isinstance(_hub, Unset):
            hub = UNSET
        else:
            hub = JsonApiRelationshipsLinksInternalResource.from_dict(_hub)

        _issues = d.pop("issues", UNSET)
        issues: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_issues, Unset):
            issues = UNSET
        else:
            issues = JsonApiRelationshipsLinksOnlyBim.from_dict(_issues)

        _locations = d.pop("locations", UNSET)
        locations: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_locations, Unset):
            locations = UNSET
        else:
            locations = JsonApiRelationshipsLinksOnlyBim.from_dict(_locations)

        _markups = d.pop("markups", UNSET)
        markups: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_markups, Unset):
            markups = UNSET
        else:
            markups = JsonApiRelationshipsLinksOnlyBim.from_dict(_markups)

        _rfis = d.pop("rfis", UNSET)
        rfis: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_rfis, Unset):
            rfis = UNSET
        else:
            rfis = JsonApiRelationshipsLinksOnlyBim.from_dict(_rfis)

        _root_folder = d.pop("rootFolder", UNSET)
        root_folder: JsonApiRelationshipsLinksRootFolder | Unset
        if isinstance(_root_folder, Unset):
            root_folder = UNSET
        else:
            root_folder = JsonApiRelationshipsLinksRootFolder.from_dict(_root_folder)

        _submittals = d.pop("submittals", UNSET)
        submittals: JsonApiRelationshipsLinksOnlyBim | Unset
        if isinstance(_submittals, Unset):
            submittals = UNSET
        else:
            submittals = JsonApiRelationshipsLinksOnlyBim.from_dict(_submittals)

        _top_folders = d.pop("topFolders", UNSET)
        top_folders: ProjectDataRelationshipsTopFolders | Unset
        if isinstance(_top_folders, Unset):
            top_folders = UNSET
        else:
            top_folders = ProjectDataRelationshipsTopFolders.from_dict(_top_folders)

        project_data_relationships = cls(
            checklists=checklists,
            cost=cost,
            hub=hub,
            issues=issues,
            locations=locations,
            markups=markups,
            rfis=rfis,
            root_folder=root_folder,
            submittals=submittals,
            top_folders=top_folders,
        )

        project_data_relationships.additional_properties = d
        return project_data_relationships

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
