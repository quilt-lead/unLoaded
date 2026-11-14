from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issue_custom_attributes_item import IssueCustomAttributesItem
    from ..models.issue_gps_coordinates import IssueGpsCoordinates
    from ..models.issue_linked_documents_item import IssueLinkedDocumentsItem
    from ..models.issue_links_item import IssueLinksItem
    from ..models.issue_official_response import IssueOfficialResponse
    from ..models.issue_permitted_actions import IssuePermittedActions


T = TypeVar("T", bound="Issue")


@_attrs_define
class Issue:
    """
    Attributes:
        assigned_to (str | Unset): The Autodesk ID of the member, role, or company you want to assign to the issue. Note
            that if you select an assignee ID, you also need to select a type (assignedToType).
        assigned_to_type (str | Unset): The type of the current assignee of this issue. Possible values: user, company,
            role, null. Note that if you select a type, you also need to select the assignee ID (assignedTo).
        attachment_count (int | Unset): Not relevant
        closed_at (str | Unset): The date and time the issue was closed, in ISO8601 format.
        closed_by (str | Unset): The unique identifier of the user who closed the issue.
        comment_count (int | Unset): The number of comments in this issue.
        container_id (str | Unset): Not relevant
        created_at (str | Unset): The date and time the issue was created, in ISO8601 format.
        created_by (str | Unset): The unique identifier of the user who created the issue
        custom_attributes (list[IssueCustomAttributesItem] | Unset): A list of custom attributes of the specific issue.
        deleted (bool | Unset): States whether the issue was deleted. Default value: false.
        deleted_at (str | Unset): The date and time the issue was deleted, in ISO8601 format. This is only relevant for
            deleted issues.
        deleted_by (str | Unset): The Autodesk ID of the user who deleted the issue. This is only relevant for deleted
            issues.
        description (str | Unset): The description and purpose of the issue.
            Max length: 10000
        display_id (int | Unset): The chronological user-friendly identifier of the issue.
        due_date (str | Unset): The due date of the issue, in ISO8601 format.
        gps_coordinates (IssueGpsCoordinates | Unset): A GPS Coordinate which represents the geo location of the issue.
        id (str | Unset): The unique identifier of the issue.
        issue_subtype_id (str | Unset): The unique identifier of the subtype of the issue.
        issue_template_id (str | Unset): Not relevant
        issue_type_id (str | Unset): The unique identifier of the type of the issue.
        linked_documents (list[IssueLinkedDocumentsItem] | Unset): Information about the files associated with issues
            (pushpins).
        links (list[IssueLinksItem] | Unset): Not relevant
        location_details (str | Unset): The location as plain text that relates to the issue.
            Max length: 8300
        location_id (str | Unset): The unique LBS (Location Breakdown Structure) identifier that relates to the issue.
        official_response (IssueOfficialResponse | Unset): Not relevant
        opened_at (str | Unset): Not relevant
        opened_by (str | Unset): Not relevant
        owner_id (str | Unset): Not relevant
        permitted_actions (IssuePermittedActions | Unset): The list of actions permitted for the user for this issue in
            its current state.
            Note that if a user with Create for my company permissions attempts to assign a user from a another company to
            the issue, it will return an error.

            Possible Values: assign_all (can assign another user from another company to the issue), assign_same_company
            (can only assign another user from the same company to the issue), clear_assignee, delete, add_comment,
            add_attachment, remove_attachment.

            The following values are not relevant: add_attachment, remove_attachment.
        permitted_attributes (list[str] | Unset): A list of attributes the current user can manipulate in the current
            context. issueTypeId, linkedDocument, links, ownerId, officialResponse, rootCauseId, snapshotUrn are not
            applicable.
        permitted_statuses (list[str] | Unset): A list of statuses accessible to the current user, this is based on the
            current status of the issue and the user permissions.
            Possible Values: open, pending, in_review, closed.
        published (bool | Unset): States whether the issue is published. Default value: false (e.g. unpublished).
        root_cause_id (str | Unset): The unique identifier of the type of root cause for the issue.
        snapshot_has_markups (bool | Unset): Not relevant
        snapshot_urn (str | Unset): Not relevant
        start_date (str | Unset): The start date of the issue, in ISO8601 format.
        status (str | Unset):
        title (str | Unset): The description and purpose of the issue.
            Max length: 10000
        updated_at (str | Unset): The date and time the issue was updated, in ISO8601 format.
        updated_by (str | Unset): The unique identifier of the user who updated the issue.
        watchers (list[str] | Unset): The Autodesk ID of the member you want to assign as a watcher for the issue.
    """

    assigned_to: str | Unset = UNSET
    assigned_to_type: str | Unset = UNSET
    attachment_count: int | Unset = UNSET
    closed_at: str | Unset = UNSET
    closed_by: str | Unset = UNSET
    comment_count: int | Unset = UNSET
    container_id: str | Unset = UNSET
    created_at: str | Unset = UNSET
    created_by: str | Unset = UNSET
    custom_attributes: list[IssueCustomAttributesItem] | Unset = UNSET
    deleted: bool | Unset = UNSET
    deleted_at: str | Unset = UNSET
    deleted_by: str | Unset = UNSET
    description: str | Unset = UNSET
    display_id: int | Unset = UNSET
    due_date: str | Unset = UNSET
    gps_coordinates: IssueGpsCoordinates | Unset = UNSET
    id: str | Unset = UNSET
    issue_subtype_id: str | Unset = UNSET
    issue_template_id: str | Unset = UNSET
    issue_type_id: str | Unset = UNSET
    linked_documents: list[IssueLinkedDocumentsItem] | Unset = UNSET
    links: list[IssueLinksItem] | Unset = UNSET
    location_details: str | Unset = UNSET
    location_id: str | Unset = UNSET
    official_response: IssueOfficialResponse | Unset = UNSET
    opened_at: str | Unset = UNSET
    opened_by: str | Unset = UNSET
    owner_id: str | Unset = UNSET
    permitted_actions: IssuePermittedActions | Unset = UNSET
    permitted_attributes: list[str] | Unset = UNSET
    permitted_statuses: list[str] | Unset = UNSET
    published: bool | Unset = UNSET
    root_cause_id: str | Unset = UNSET
    snapshot_has_markups: bool | Unset = UNSET
    snapshot_urn: str | Unset = UNSET
    start_date: str | Unset = UNSET
    status: str | Unset = UNSET
    title: str | Unset = UNSET
    updated_at: str | Unset = UNSET
    updated_by: str | Unset = UNSET
    watchers: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        assigned_to = self.assigned_to

        assigned_to_type = self.assigned_to_type

        attachment_count = self.attachment_count

        closed_at = self.closed_at

        closed_by = self.closed_by

        comment_count = self.comment_count

        container_id = self.container_id

        created_at = self.created_at

        created_by = self.created_by

        custom_attributes: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.custom_attributes, Unset):
            custom_attributes = []
            for custom_attributes_item_data in self.custom_attributes:
                custom_attributes_item = custom_attributes_item_data.to_dict()
                custom_attributes.append(custom_attributes_item)

        deleted = self.deleted

        deleted_at = self.deleted_at

        deleted_by = self.deleted_by

        description = self.description

        display_id = self.display_id

        due_date = self.due_date

        gps_coordinates: dict[str, Any] | Unset = UNSET
        if not isinstance(self.gps_coordinates, Unset):
            gps_coordinates = self.gps_coordinates.to_dict()

        id = self.id

        issue_subtype_id = self.issue_subtype_id

        issue_template_id = self.issue_template_id

        issue_type_id = self.issue_type_id

        linked_documents: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.linked_documents, Unset):
            linked_documents = []
            for linked_documents_item_data in self.linked_documents:
                linked_documents_item = linked_documents_item_data.to_dict()
                linked_documents.append(linked_documents_item)

        links: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.links, Unset):
            links = []
            for links_item_data in self.links:
                links_item = links_item_data.to_dict()
                links.append(links_item)

        location_details = self.location_details

        location_id = self.location_id

        official_response: dict[str, Any] | Unset = UNSET
        if not isinstance(self.official_response, Unset):
            official_response = self.official_response.to_dict()

        opened_at = self.opened_at

        opened_by = self.opened_by

        owner_id = self.owner_id

        permitted_actions: dict[str, Any] | Unset = UNSET
        if not isinstance(self.permitted_actions, Unset):
            permitted_actions = self.permitted_actions.to_dict()

        permitted_attributes: list[str] | Unset = UNSET
        if not isinstance(self.permitted_attributes, Unset):
            permitted_attributes = self.permitted_attributes

        permitted_statuses: list[str] | Unset = UNSET
        if not isinstance(self.permitted_statuses, Unset):
            permitted_statuses = self.permitted_statuses

        published = self.published

        root_cause_id = self.root_cause_id

        snapshot_has_markups = self.snapshot_has_markups

        snapshot_urn = self.snapshot_urn

        start_date = self.start_date

        status = self.status

        title = self.title

        updated_at = self.updated_at

        updated_by = self.updated_by

        watchers: list[str] | Unset = UNSET
        if not isinstance(self.watchers, Unset):
            watchers = self.watchers

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if assigned_to is not UNSET:
            field_dict["assignedTo"] = assigned_to
        if assigned_to_type is not UNSET:
            field_dict["assignedToType"] = assigned_to_type
        if attachment_count is not UNSET:
            field_dict["attachmentCount"] = attachment_count
        if closed_at is not UNSET:
            field_dict["closedAt"] = closed_at
        if closed_by is not UNSET:
            field_dict["closedBy"] = closed_by
        if comment_count is not UNSET:
            field_dict["commentCount"] = comment_count
        if container_id is not UNSET:
            field_dict["containerId"] = container_id
        if created_at is not UNSET:
            field_dict["createdAt"] = created_at
        if created_by is not UNSET:
            field_dict["createdBy"] = created_by
        if custom_attributes is not UNSET:
            field_dict["customAttributes"] = custom_attributes
        if deleted is not UNSET:
            field_dict["deleted"] = deleted
        if deleted_at is not UNSET:
            field_dict["deletedAt"] = deleted_at
        if deleted_by is not UNSET:
            field_dict["deletedBy"] = deleted_by
        if description is not UNSET:
            field_dict["description"] = description
        if display_id is not UNSET:
            field_dict["displayId"] = display_id
        if due_date is not UNSET:
            field_dict["dueDate"] = due_date
        if gps_coordinates is not UNSET:
            field_dict["gpsCoordinates"] = gps_coordinates
        if id is not UNSET:
            field_dict["id"] = id
        if issue_subtype_id is not UNSET:
            field_dict["issueSubtypeId"] = issue_subtype_id
        if issue_template_id is not UNSET:
            field_dict["issueTemplateId"] = issue_template_id
        if issue_type_id is not UNSET:
            field_dict["issueTypeId"] = issue_type_id
        if linked_documents is not UNSET:
            field_dict["linkedDocuments"] = linked_documents
        if links is not UNSET:
            field_dict["links"] = links
        if location_details is not UNSET:
            field_dict["locationDetails"] = location_details
        if location_id is not UNSET:
            field_dict["locationId"] = location_id
        if official_response is not UNSET:
            field_dict["officialResponse"] = official_response
        if opened_at is not UNSET:
            field_dict["openedAt"] = opened_at
        if opened_by is not UNSET:
            field_dict["openedBy"] = opened_by
        if owner_id is not UNSET:
            field_dict["ownerId"] = owner_id
        if permitted_actions is not UNSET:
            field_dict["permittedActions"] = permitted_actions
        if permitted_attributes is not UNSET:
            field_dict["permittedAttributes"] = permitted_attributes
        if permitted_statuses is not UNSET:
            field_dict["permittedStatuses"] = permitted_statuses
        if published is not UNSET:
            field_dict["published"] = published
        if root_cause_id is not UNSET:
            field_dict["rootCauseId"] = root_cause_id
        if snapshot_has_markups is not UNSET:
            field_dict["snapshotHasMarkups"] = snapshot_has_markups
        if snapshot_urn is not UNSET:
            field_dict["snapshotUrn"] = snapshot_urn
        if start_date is not UNSET:
            field_dict["startDate"] = start_date
        if status is not UNSET:
            field_dict["status"] = status
        if title is not UNSET:
            field_dict["title"] = title
        if updated_at is not UNSET:
            field_dict["updatedAt"] = updated_at
        if updated_by is not UNSET:
            field_dict["updatedBy"] = updated_by
        if watchers is not UNSET:
            field_dict["watchers"] = watchers

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_custom_attributes_item import IssueCustomAttributesItem
        from ..models.issue_gps_coordinates import IssueGpsCoordinates
        from ..models.issue_linked_documents_item import IssueLinkedDocumentsItem
        from ..models.issue_links_item import IssueLinksItem
        from ..models.issue_official_response import IssueOfficialResponse
        from ..models.issue_permitted_actions import IssuePermittedActions

        d = dict(src_dict)
        assigned_to = d.pop("assignedTo", UNSET)

        assigned_to_type = d.pop("assignedToType", UNSET)

        attachment_count = d.pop("attachmentCount", UNSET)

        closed_at = d.pop("closedAt", UNSET)

        closed_by = d.pop("closedBy", UNSET)

        comment_count = d.pop("commentCount", UNSET)

        container_id = d.pop("containerId", UNSET)

        created_at = d.pop("createdAt", UNSET)

        created_by = d.pop("createdBy", UNSET)

        _custom_attributes = d.pop("customAttributes", UNSET)
        custom_attributes: list[IssueCustomAttributesItem] | Unset = UNSET
        if _custom_attributes is not UNSET:
            custom_attributes = []
            for custom_attributes_item_data in _custom_attributes:
                custom_attributes_item = IssueCustomAttributesItem.from_dict(
                    custom_attributes_item_data
                )

                custom_attributes.append(custom_attributes_item)

        deleted = d.pop("deleted", UNSET)

        deleted_at = d.pop("deletedAt", UNSET)

        deleted_by = d.pop("deletedBy", UNSET)

        description = d.pop("description", UNSET)

        display_id = d.pop("displayId", UNSET)

        due_date = d.pop("dueDate", UNSET)

        _gps_coordinates = d.pop("gpsCoordinates", UNSET)
        gps_coordinates: IssueGpsCoordinates | Unset
        if isinstance(_gps_coordinates, Unset):
            gps_coordinates = UNSET
        else:
            gps_coordinates = IssueGpsCoordinates.from_dict(_gps_coordinates)

        id = d.pop("id", UNSET)

        issue_subtype_id = d.pop("issueSubtypeId", UNSET)

        issue_template_id = d.pop("issueTemplateId", UNSET)

        issue_type_id = d.pop("issueTypeId", UNSET)

        _linked_documents = d.pop("linkedDocuments", UNSET)
        linked_documents: list[IssueLinkedDocumentsItem] | Unset = UNSET
        if _linked_documents is not UNSET:
            linked_documents = []
            for linked_documents_item_data in _linked_documents:
                linked_documents_item = IssueLinkedDocumentsItem.from_dict(
                    linked_documents_item_data
                )

                linked_documents.append(linked_documents_item)

        _links = d.pop("links", UNSET)
        links: list[IssueLinksItem] | Unset = UNSET
        if _links is not UNSET:
            links = []
            for links_item_data in _links:
                links_item = IssueLinksItem.from_dict(links_item_data)

                links.append(links_item)

        location_details = d.pop("locationDetails", UNSET)

        location_id = d.pop("locationId", UNSET)

        _official_response = d.pop("officialResponse", UNSET)
        official_response: IssueOfficialResponse | Unset
        if isinstance(_official_response, Unset):
            official_response = UNSET
        else:
            official_response = IssueOfficialResponse.from_dict(_official_response)

        opened_at = d.pop("openedAt", UNSET)

        opened_by = d.pop("openedBy", UNSET)

        owner_id = d.pop("ownerId", UNSET)

        _permitted_actions = d.pop("permittedActions", UNSET)
        permitted_actions: IssuePermittedActions | Unset
        if isinstance(_permitted_actions, Unset):
            permitted_actions = UNSET
        else:
            permitted_actions = IssuePermittedActions.from_dict(_permitted_actions)

        permitted_attributes = cast(list[str], d.pop("permittedAttributes", UNSET))

        permitted_statuses = cast(list[str], d.pop("permittedStatuses", UNSET))

        published = d.pop("published", UNSET)

        root_cause_id = d.pop("rootCauseId", UNSET)

        snapshot_has_markups = d.pop("snapshotHasMarkups", UNSET)

        snapshot_urn = d.pop("snapshotUrn", UNSET)

        start_date = d.pop("startDate", UNSET)

        status = d.pop("status", UNSET)

        title = d.pop("title", UNSET)

        updated_at = d.pop("updatedAt", UNSET)

        updated_by = d.pop("updatedBy", UNSET)

        watchers = cast(list[str], d.pop("watchers", UNSET))

        issue = cls(
            assigned_to=assigned_to,
            assigned_to_type=assigned_to_type,
            attachment_count=attachment_count,
            closed_at=closed_at,
            closed_by=closed_by,
            comment_count=comment_count,
            container_id=container_id,
            created_at=created_at,
            created_by=created_by,
            custom_attributes=custom_attributes,
            deleted=deleted,
            deleted_at=deleted_at,
            deleted_by=deleted_by,
            description=description,
            display_id=display_id,
            due_date=due_date,
            gps_coordinates=gps_coordinates,
            id=id,
            issue_subtype_id=issue_subtype_id,
            issue_template_id=issue_template_id,
            issue_type_id=issue_type_id,
            linked_documents=linked_documents,
            links=links,
            location_details=location_details,
            location_id=location_id,
            official_response=official_response,
            opened_at=opened_at,
            opened_by=opened_by,
            owner_id=owner_id,
            permitted_actions=permitted_actions,
            permitted_attributes=permitted_attributes,
            permitted_statuses=permitted_statuses,
            published=published,
            root_cause_id=root_cause_id,
            snapshot_has_markups=snapshot_has_markups,
            snapshot_urn=snapshot_urn,
            start_date=start_date,
            status=status,
            title=title,
            updated_at=updated_at,
            updated_by=updated_by,
            watchers=watchers,
        )

        issue.additional_properties = d
        return issue

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
