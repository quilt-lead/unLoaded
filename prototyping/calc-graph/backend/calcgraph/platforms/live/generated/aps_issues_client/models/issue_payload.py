from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.assigned_to_type import AssignedToType
from ..models.status import Status
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issue_payload_custom_attributes_item import (
        IssuePayloadCustomAttributesItem,
    )
    from ..models.issue_payload_gps_coordinates import IssuePayloadGpsCoordinates
    from ..models.issue_payload_permitted_actions import IssuePayloadPermittedActions


T = TypeVar("T", bound="IssuePayload")


@_attrs_define
class IssuePayload:
    """
    Attributes:
        issue_subtype_id (str): The unique identifier of the subtype of the issue.
        status (Status): The current status of the issue. To check the available statuses for the project, call GET
            users/me and check the permitted statuses list (issue.new.permittedStatuses). For more information about
            statuses, see the Help documentation.
        title (str): The description and purpose of the issue.
            Max length: 10000
        assigned_to (str | Unset): The Autodesk ID of the member, role, or company you want to assign to the issue. Note
            that if you select an assignee ID, you also need to select a type (assignedToType).
        assigned_to_type (AssignedToType | Unset):
        custom_attributes (list[IssuePayloadCustomAttributesItem] | Unset): A list of custom attributes of the specific
            issue.
        description (str | Unset): The description and purpose of the issue.
            Max length: 10000
        due_date (str | Unset): The due date of the issue, in ISO8601 format.
        gps_coordinates (IssuePayloadGpsCoordinates | Unset): A GPS Coordinate which represents the geo location of the
            issue.
        issue_template_id (str | Unset): The unique identifier of the type of root cause for the issue.
        location_details (str | Unset): The location as plain text that relates to the issue.
            Max length: 8300
        location_id (str | Unset): The unique LBS (Location Breakdown Structure) identifier that relates to the issue.
        permitted_actions (IssuePayloadPermittedActions | Unset): The list of actions permitted for the user for this
            issue in its current state.
            Note that if a user with Create for my company permissions attempts to assign a user from a another company to
            the issue, it will return an error.

            Possible Values: assign_all (can assign another user from another company to the issue), assign_same_company
            (can only assign another user from the same company to the issue), clear_assignee, delete, add_comment,
            add_attachment, remove_attachment.

            The following values are not relevant: add_attachment, remove_attachment.
        published (bool | Unset): States whether the issue is published. Default value: false (e.g. unpublished).
        root_cause_id (str | Unset): The unique identifier of the type of root cause for the issue.
        snapshot_urn (str | Unset): Not relevant
        start_date (str | Unset): The start date of the issue, in ISO8601 format.
        watchers (list[str] | Unset): The Autodesk ID of the member you want to assign as a watcher for the issue.
    """

    issue_subtype_id: str
    status: Status
    title: str
    assigned_to: str | Unset = UNSET
    assigned_to_type: AssignedToType | Unset = UNSET
    custom_attributes: list[IssuePayloadCustomAttributesItem] | Unset = UNSET
    description: str | Unset = UNSET
    due_date: str | Unset = UNSET
    gps_coordinates: IssuePayloadGpsCoordinates | Unset = UNSET
    issue_template_id: str | Unset = UNSET
    location_details: str | Unset = UNSET
    location_id: str | Unset = UNSET
    permitted_actions: IssuePayloadPermittedActions | Unset = UNSET
    published: bool | Unset = UNSET
    root_cause_id: str | Unset = UNSET
    snapshot_urn: str | Unset = UNSET
    start_date: str | Unset = UNSET
    watchers: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        issue_subtype_id = self.issue_subtype_id

        status = self.status.value

        title = self.title

        assigned_to = self.assigned_to

        assigned_to_type: str | Unset = UNSET
        if not isinstance(self.assigned_to_type, Unset):
            assigned_to_type = self.assigned_to_type.value

        custom_attributes: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.custom_attributes, Unset):
            custom_attributes = []
            for custom_attributes_item_data in self.custom_attributes:
                custom_attributes_item = custom_attributes_item_data.to_dict()
                custom_attributes.append(custom_attributes_item)

        description = self.description

        due_date = self.due_date

        gps_coordinates: dict[str, Any] | Unset = UNSET
        if not isinstance(self.gps_coordinates, Unset):
            gps_coordinates = self.gps_coordinates.to_dict()

        issue_template_id = self.issue_template_id

        location_details = self.location_details

        location_id = self.location_id

        permitted_actions: dict[str, Any] | Unset = UNSET
        if not isinstance(self.permitted_actions, Unset):
            permitted_actions = self.permitted_actions.to_dict()

        published = self.published

        root_cause_id = self.root_cause_id

        snapshot_urn = self.snapshot_urn

        start_date = self.start_date

        watchers: list[str] | Unset = UNSET
        if not isinstance(self.watchers, Unset):
            watchers = self.watchers

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "issueSubtypeId": issue_subtype_id,
                "status": status,
                "title": title,
            }
        )
        if assigned_to is not UNSET:
            field_dict["assignedTo"] = assigned_to
        if assigned_to_type is not UNSET:
            field_dict["assignedToType"] = assigned_to_type
        if custom_attributes is not UNSET:
            field_dict["customAttributes"] = custom_attributes
        if description is not UNSET:
            field_dict["description"] = description
        if due_date is not UNSET:
            field_dict["dueDate"] = due_date
        if gps_coordinates is not UNSET:
            field_dict["gpsCoordinates"] = gps_coordinates
        if issue_template_id is not UNSET:
            field_dict["issueTemplateId"] = issue_template_id
        if location_details is not UNSET:
            field_dict["locationDetails"] = location_details
        if location_id is not UNSET:
            field_dict["locationId"] = location_id
        if permitted_actions is not UNSET:
            field_dict["permittedActions"] = permitted_actions
        if published is not UNSET:
            field_dict["published"] = published
        if root_cause_id is not UNSET:
            field_dict["rootCauseId"] = root_cause_id
        if snapshot_urn is not UNSET:
            field_dict["snapshotUrn"] = snapshot_urn
        if start_date is not UNSET:
            field_dict["startDate"] = start_date
        if watchers is not UNSET:
            field_dict["watchers"] = watchers

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_payload_custom_attributes_item import (
            IssuePayloadCustomAttributesItem,
        )
        from ..models.issue_payload_gps_coordinates import IssuePayloadGpsCoordinates
        from ..models.issue_payload_permitted_actions import (
            IssuePayloadPermittedActions,
        )

        d = dict(src_dict)
        issue_subtype_id = d.pop("issueSubtypeId")

        status = Status(d.pop("status"))

        title = d.pop("title")

        assigned_to = d.pop("assignedTo", UNSET)

        _assigned_to_type = d.pop("assignedToType", UNSET)
        assigned_to_type: AssignedToType | Unset
        if isinstance(_assigned_to_type, Unset):
            assigned_to_type = UNSET
        else:
            assigned_to_type = AssignedToType(_assigned_to_type)

        _custom_attributes = d.pop("customAttributes", UNSET)
        custom_attributes: list[IssuePayloadCustomAttributesItem] | Unset = UNSET
        if _custom_attributes is not UNSET:
            custom_attributes = []
            for custom_attributes_item_data in _custom_attributes:
                custom_attributes_item = IssuePayloadCustomAttributesItem.from_dict(
                    custom_attributes_item_data
                )

                custom_attributes.append(custom_attributes_item)

        description = d.pop("description", UNSET)

        due_date = d.pop("dueDate", UNSET)

        _gps_coordinates = d.pop("gpsCoordinates", UNSET)
        gps_coordinates: IssuePayloadGpsCoordinates | Unset
        if isinstance(_gps_coordinates, Unset):
            gps_coordinates = UNSET
        else:
            gps_coordinates = IssuePayloadGpsCoordinates.from_dict(_gps_coordinates)

        issue_template_id = d.pop("issueTemplateId", UNSET)

        location_details = d.pop("locationDetails", UNSET)

        location_id = d.pop("locationId", UNSET)

        _permitted_actions = d.pop("permittedActions", UNSET)
        permitted_actions: IssuePayloadPermittedActions | Unset
        if isinstance(_permitted_actions, Unset):
            permitted_actions = UNSET
        else:
            permitted_actions = IssuePayloadPermittedActions.from_dict(
                _permitted_actions
            )

        published = d.pop("published", UNSET)

        root_cause_id = d.pop("rootCauseId", UNSET)

        snapshot_urn = d.pop("snapshotUrn", UNSET)

        start_date = d.pop("startDate", UNSET)

        watchers = cast(list[str], d.pop("watchers", UNSET))

        issue_payload = cls(
            issue_subtype_id=issue_subtype_id,
            status=status,
            title=title,
            assigned_to=assigned_to,
            assigned_to_type=assigned_to_type,
            custom_attributes=custom_attributes,
            description=description,
            due_date=due_date,
            gps_coordinates=gps_coordinates,
            issue_template_id=issue_template_id,
            location_details=location_details,
            location_id=location_id,
            permitted_actions=permitted_actions,
            published=published,
            root_cause_id=root_cause_id,
            snapshot_urn=snapshot_urn,
            start_date=start_date,
            watchers=watchers,
        )

        issue_payload.additional_properties = d
        return issue_payload

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
