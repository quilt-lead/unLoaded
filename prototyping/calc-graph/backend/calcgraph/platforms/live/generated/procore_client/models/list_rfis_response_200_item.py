from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_rfis_response_200_item_status import ListRfisResponse200ItemStatus
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_rfis_response_200_item_assignee import (
        ListRfisResponse200ItemAssignee,
    )
    from ..models.list_rfis_response_200_item_assignees_item import (
        ListRfisResponse200ItemAssigneesItem,
    )
    from ..models.list_rfis_response_200_item_ball_in_court import (
        ListRfisResponse200ItemBallInCourt,
    )
    from ..models.list_rfis_response_200_item_ball_in_courts_item import (
        ListRfisResponse200ItemBallInCourtsItem,
    )
    from ..models.list_rfis_response_200_item_connect_export_origin_type_0 import (
        ListRfisResponse200ItemConnectExportOriginType0,
    )
    from ..models.list_rfis_response_200_item_cost_code import (
        ListRfisResponse200ItemCostCode,
    )
    from ..models.list_rfis_response_200_item_cost_impact import (
        ListRfisResponse200ItemCostImpact,
    )
    from ..models.list_rfis_response_200_item_created_by import (
        ListRfisResponse200ItemCreatedBy,
    )
    from ..models.list_rfis_response_200_item_custom_fields import (
        ListRfisResponse200ItemCustomFields,
    )
    from ..models.list_rfis_response_200_item_location import (
        ListRfisResponse200ItemLocation,
    )
    from ..models.list_rfis_response_200_item_project_stage import (
        ListRfisResponse200ItemProjectStage,
    )
    from ..models.list_rfis_response_200_item_questions_item import (
        ListRfisResponse200ItemQuestionsItem,
    )
    from ..models.list_rfis_response_200_item_received_from import (
        ListRfisResponse200ItemReceivedFrom,
    )
    from ..models.list_rfis_response_200_item_responsible_contractor import (
        ListRfisResponse200ItemResponsibleContractor,
    )
    from ..models.list_rfis_response_200_item_rfi_manager import (
        ListRfisResponse200ItemRfiManager,
    )
    from ..models.list_rfis_response_200_item_schedule_impact import (
        ListRfisResponse200ItemScheduleImpact,
    )
    from ..models.list_rfis_response_200_item_sub_job import (
        ListRfisResponse200ItemSubJob,
    )


T = TypeVar("T", bound="ListRfisResponse200Item")


@_attrs_define
class ListRfisResponse200Item:
    """
    Attributes:
        assignee (ListRfisResponse200ItemAssignee | Unset):
        assignees (list[ListRfisResponse200ItemAssigneesItem] | Unset): RFI Assignees
        ball_in_court (ListRfisResponse200ItemBallInCourt | Unset):
        ball_in_courts (list[ListRfisResponse200ItemBallInCourtsItem] | Unset): Ball In Courts
        connect_export_origin (ListRfisResponse200ItemConnectExportOriginType0 | None | Unset): Export origin
            information for RFIs received via cross-account collaboration. Null for RFIs not received via export.
        cost_code (ListRfisResponse200ItemCostCode | Unset):
        cost_impact (ListRfisResponse200ItemCostImpact | Unset):
        created_at (datetime.datetime | Unset): Date created
        created_by (ListRfisResponse200ItemCreatedBy | Unset):
        current_revision (bool | Unset): Designate whether or not this RFI is the latest revision
        custom_fields (ListRfisResponse200ItemCustomFields | Unset):
        deleted (bool | Unset): Deleted status (this is only shown on deleted records)
        deleted_at (datetime.datetime | Unset): Time deleted (this is only shown on deleted records)
        due_date (datetime.date | datetime.datetime | Unset): Due Date
        full_number (str | Unset): Full Number
        has_revisions (bool | Unset): Designate whether or not this RFI has other revisions
        id (int | Unset): ID
        initiated_at (datetime.datetime | Unset): Date initiated
        link (str | Unset): Web link to resource
        location (ListRfisResponse200ItemLocation | Unset):
        location_id (int | Unset): ID of the associated Location
        number (str | Unset): Number
        prefix (str | Unset): Prefix
        private (bool | Unset): Private Status
        project_stage (ListRfisResponse200ItemProjectStage | Unset):
        questions (list[ListRfisResponse200ItemQuestionsItem] | Unset): RFI Questions
        received_from (ListRfisResponse200ItemReceivedFrom | Unset):
        reference (str | Unset): Reference
        responsible_contractor (ListRfisResponse200ItemResponsibleContractor | Unset):
        revision (str | Unset): Revision Number
        rfi_manager (ListRfisResponse200ItemRfiManager | Unset):
        schedule_impact (ListRfisResponse200ItemScheduleImpact | Unset):
        source_rfi_header_id (int | Unset): The ID of The Root RFI Revision
        specification_section_id (int | Unset): ID of the associated Specification Section
        status (ListRfisResponse200ItemStatus | Unset): Status
        sub_job (ListRfisResponse200ItemSubJob | Unset):
        subject (str | Unset): Subject
        time_resolved (datetime.datetime | Unset): Time RFI was closed
        translated_status (str | Unset): Translated RFI status
        updated_at (datetime.datetime | Unset): Updated at
    """

    assignee: ListRfisResponse200ItemAssignee | Unset = UNSET
    assignees: list[ListRfisResponse200ItemAssigneesItem] | Unset = UNSET
    ball_in_court: ListRfisResponse200ItemBallInCourt | Unset = UNSET
    ball_in_courts: list[ListRfisResponse200ItemBallInCourtsItem] | Unset = UNSET
    connect_export_origin: (
        ListRfisResponse200ItemConnectExportOriginType0 | None | Unset
    ) = UNSET
    cost_code: ListRfisResponse200ItemCostCode | Unset = UNSET
    cost_impact: ListRfisResponse200ItemCostImpact | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: ListRfisResponse200ItemCreatedBy | Unset = UNSET
    current_revision: bool | Unset = UNSET
    custom_fields: ListRfisResponse200ItemCustomFields | Unset = UNSET
    deleted: bool | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    due_date: datetime.date | datetime.datetime | Unset = UNSET
    full_number: str | Unset = UNSET
    has_revisions: bool | Unset = UNSET
    id: int | Unset = UNSET
    initiated_at: datetime.datetime | Unset = UNSET
    link: str | Unset = UNSET
    location: ListRfisResponse200ItemLocation | Unset = UNSET
    location_id: int | Unset = UNSET
    number: str | Unset = UNSET
    prefix: str | Unset = UNSET
    private: bool | Unset = UNSET
    project_stage: ListRfisResponse200ItemProjectStage | Unset = UNSET
    questions: list[ListRfisResponse200ItemQuestionsItem] | Unset = UNSET
    received_from: ListRfisResponse200ItemReceivedFrom | Unset = UNSET
    reference: str | Unset = UNSET
    responsible_contractor: ListRfisResponse200ItemResponsibleContractor | Unset = UNSET
    revision: str | Unset = UNSET
    rfi_manager: ListRfisResponse200ItemRfiManager | Unset = UNSET
    schedule_impact: ListRfisResponse200ItemScheduleImpact | Unset = UNSET
    source_rfi_header_id: int | Unset = UNSET
    specification_section_id: int | Unset = UNSET
    status: ListRfisResponse200ItemStatus | Unset = UNSET
    sub_job: ListRfisResponse200ItemSubJob | Unset = UNSET
    subject: str | Unset = UNSET
    time_resolved: datetime.datetime | Unset = UNSET
    translated_status: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.list_rfis_response_200_item_connect_export_origin_type_0 import (
            ListRfisResponse200ItemConnectExportOriginType0,
        )

        assignee: dict[str, Any] | Unset = UNSET
        if not isinstance(self.assignee, Unset):
            assignee = self.assignee.to_dict()

        assignees: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.assignees, Unset):
            assignees = []
            for assignees_item_data in self.assignees:
                assignees_item = assignees_item_data.to_dict()
                assignees.append(assignees_item)

        ball_in_court: dict[str, Any] | Unset = UNSET
        if not isinstance(self.ball_in_court, Unset):
            ball_in_court = self.ball_in_court.to_dict()

        ball_in_courts: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.ball_in_courts, Unset):
            ball_in_courts = []
            for ball_in_courts_item_data in self.ball_in_courts:
                ball_in_courts_item = ball_in_courts_item_data.to_dict()
                ball_in_courts.append(ball_in_courts_item)

        connect_export_origin: dict[str, Any] | None | Unset
        if isinstance(self.connect_export_origin, Unset):
            connect_export_origin = UNSET
        elif isinstance(
            self.connect_export_origin, ListRfisResponse200ItemConnectExportOriginType0
        ):
            connect_export_origin = self.connect_export_origin.to_dict()
        else:
            connect_export_origin = self.connect_export_origin

        cost_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_code, Unset):
            cost_code = self.cost_code.to_dict()

        cost_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_impact, Unset):
            cost_impact = self.cost_impact.to_dict()

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        created_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.created_by, Unset):
            created_by = self.created_by.to_dict()

        current_revision = self.current_revision

        custom_fields: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_fields, Unset):
            custom_fields = self.custom_fields.to_dict()

        deleted = self.deleted

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        due_date: str | Unset
        if isinstance(self.due_date, Unset):
            due_date = UNSET
        elif isinstance(self.due_date, datetime.date):
            due_date = self.due_date.isoformat()
        else:
            due_date = self.due_date.isoformat()

        full_number = self.full_number

        has_revisions = self.has_revisions

        id = self.id

        initiated_at: str | Unset = UNSET
        if not isinstance(self.initiated_at, Unset):
            initiated_at = self.initiated_at.isoformat()

        link = self.link

        location: dict[str, Any] | Unset = UNSET
        if not isinstance(self.location, Unset):
            location = self.location.to_dict()

        location_id = self.location_id

        number = self.number

        prefix = self.prefix

        private = self.private

        project_stage: dict[str, Any] | Unset = UNSET
        if not isinstance(self.project_stage, Unset):
            project_stage = self.project_stage.to_dict()

        questions: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.questions, Unset):
            questions = []
            for questions_item_data in self.questions:
                questions_item = questions_item_data.to_dict()
                questions.append(questions_item)

        received_from: dict[str, Any] | Unset = UNSET
        if not isinstance(self.received_from, Unset):
            received_from = self.received_from.to_dict()

        reference = self.reference

        responsible_contractor: dict[str, Any] | Unset = UNSET
        if not isinstance(self.responsible_contractor, Unset):
            responsible_contractor = self.responsible_contractor.to_dict()

        revision = self.revision

        rfi_manager: dict[str, Any] | Unset = UNSET
        if not isinstance(self.rfi_manager, Unset):
            rfi_manager = self.rfi_manager.to_dict()

        schedule_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.schedule_impact, Unset):
            schedule_impact = self.schedule_impact.to_dict()

        source_rfi_header_id = self.source_rfi_header_id

        specification_section_id = self.specification_section_id

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        sub_job: dict[str, Any] | Unset = UNSET
        if not isinstance(self.sub_job, Unset):
            sub_job = self.sub_job.to_dict()

        subject = self.subject

        time_resolved: str | Unset = UNSET
        if not isinstance(self.time_resolved, Unset):
            time_resolved = self.time_resolved.isoformat()

        translated_status = self.translated_status

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if assignee is not UNSET:
            field_dict["assignee"] = assignee
        if assignees is not UNSET:
            field_dict["assignees"] = assignees
        if ball_in_court is not UNSET:
            field_dict["ball_in_court"] = ball_in_court
        if ball_in_courts is not UNSET:
            field_dict["ball_in_courts"] = ball_in_courts
        if connect_export_origin is not UNSET:
            field_dict["connect_export_origin"] = connect_export_origin
        if cost_code is not UNSET:
            field_dict["cost_code"] = cost_code
        if cost_impact is not UNSET:
            field_dict["cost_impact"] = cost_impact
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if current_revision is not UNSET:
            field_dict["current_revision"] = current_revision
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if deleted is not UNSET:
            field_dict["deleted"] = deleted
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if full_number is not UNSET:
            field_dict["full_number"] = full_number
        if has_revisions is not UNSET:
            field_dict["has_revisions"] = has_revisions
        if id is not UNSET:
            field_dict["id"] = id
        if initiated_at is not UNSET:
            field_dict["initiated_at"] = initiated_at
        if link is not UNSET:
            field_dict["link"] = link
        if location is not UNSET:
            field_dict["location"] = location
        if location_id is not UNSET:
            field_dict["location_id"] = location_id
        if number is not UNSET:
            field_dict["number"] = number
        if prefix is not UNSET:
            field_dict["prefix"] = prefix
        if private is not UNSET:
            field_dict["private"] = private
        if project_stage is not UNSET:
            field_dict["project_stage"] = project_stage
        if questions is not UNSET:
            field_dict["questions"] = questions
        if received_from is not UNSET:
            field_dict["received_from"] = received_from
        if reference is not UNSET:
            field_dict["reference"] = reference
        if responsible_contractor is not UNSET:
            field_dict["responsible_contractor"] = responsible_contractor
        if revision is not UNSET:
            field_dict["revision"] = revision
        if rfi_manager is not UNSET:
            field_dict["rfi_manager"] = rfi_manager
        if schedule_impact is not UNSET:
            field_dict["schedule_impact"] = schedule_impact
        if source_rfi_header_id is not UNSET:
            field_dict["source_rfi_header_id"] = source_rfi_header_id
        if specification_section_id is not UNSET:
            field_dict["specification_section_id"] = specification_section_id
        if status is not UNSET:
            field_dict["status"] = status
        if sub_job is not UNSET:
            field_dict["sub_job"] = sub_job
        if subject is not UNSET:
            field_dict["subject"] = subject
        if time_resolved is not UNSET:
            field_dict["time_resolved"] = time_resolved
        if translated_status is not UNSET:
            field_dict["translated_status"] = translated_status
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_rfis_response_200_item_assignee import (
            ListRfisResponse200ItemAssignee,
        )
        from ..models.list_rfis_response_200_item_assignees_item import (
            ListRfisResponse200ItemAssigneesItem,
        )
        from ..models.list_rfis_response_200_item_ball_in_court import (
            ListRfisResponse200ItemBallInCourt,
        )
        from ..models.list_rfis_response_200_item_ball_in_courts_item import (
            ListRfisResponse200ItemBallInCourtsItem,
        )
        from ..models.list_rfis_response_200_item_connect_export_origin_type_0 import (
            ListRfisResponse200ItemConnectExportOriginType0,
        )
        from ..models.list_rfis_response_200_item_cost_code import (
            ListRfisResponse200ItemCostCode,
        )
        from ..models.list_rfis_response_200_item_cost_impact import (
            ListRfisResponse200ItemCostImpact,
        )
        from ..models.list_rfis_response_200_item_created_by import (
            ListRfisResponse200ItemCreatedBy,
        )
        from ..models.list_rfis_response_200_item_custom_fields import (
            ListRfisResponse200ItemCustomFields,
        )
        from ..models.list_rfis_response_200_item_location import (
            ListRfisResponse200ItemLocation,
        )
        from ..models.list_rfis_response_200_item_project_stage import (
            ListRfisResponse200ItemProjectStage,
        )
        from ..models.list_rfis_response_200_item_questions_item import (
            ListRfisResponse200ItemQuestionsItem,
        )
        from ..models.list_rfis_response_200_item_received_from import (
            ListRfisResponse200ItemReceivedFrom,
        )
        from ..models.list_rfis_response_200_item_responsible_contractor import (
            ListRfisResponse200ItemResponsibleContractor,
        )
        from ..models.list_rfis_response_200_item_rfi_manager import (
            ListRfisResponse200ItemRfiManager,
        )
        from ..models.list_rfis_response_200_item_schedule_impact import (
            ListRfisResponse200ItemScheduleImpact,
        )
        from ..models.list_rfis_response_200_item_sub_job import (
            ListRfisResponse200ItemSubJob,
        )

        d = dict(src_dict)
        _assignee = d.pop("assignee", UNSET)
        assignee: ListRfisResponse200ItemAssignee | Unset
        if isinstance(_assignee, Unset):
            assignee = UNSET
        else:
            assignee = ListRfisResponse200ItemAssignee.from_dict(_assignee)

        _assignees = d.pop("assignees", UNSET)
        assignees: list[ListRfisResponse200ItemAssigneesItem] | Unset = UNSET
        if _assignees is not UNSET:
            assignees = []
            for assignees_item_data in _assignees:
                assignees_item = ListRfisResponse200ItemAssigneesItem.from_dict(
                    assignees_item_data
                )

                assignees.append(assignees_item)

        _ball_in_court = d.pop("ball_in_court", UNSET)
        ball_in_court: ListRfisResponse200ItemBallInCourt | Unset
        if isinstance(_ball_in_court, Unset):
            ball_in_court = UNSET
        else:
            ball_in_court = ListRfisResponse200ItemBallInCourt.from_dict(_ball_in_court)

        _ball_in_courts = d.pop("ball_in_courts", UNSET)
        ball_in_courts: list[ListRfisResponse200ItemBallInCourtsItem] | Unset = UNSET
        if _ball_in_courts is not UNSET:
            ball_in_courts = []
            for ball_in_courts_item_data in _ball_in_courts:
                ball_in_courts_item = ListRfisResponse200ItemBallInCourtsItem.from_dict(
                    ball_in_courts_item_data
                )

                ball_in_courts.append(ball_in_courts_item)

        def _parse_connect_export_origin(
            data: object,
        ) -> ListRfisResponse200ItemConnectExportOriginType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                connect_export_origin_type_0 = (
                    ListRfisResponse200ItemConnectExportOriginType0.from_dict(data)
                )

                return connect_export_origin_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListRfisResponse200ItemConnectExportOriginType0 | None | Unset, data
            )

        connect_export_origin = _parse_connect_export_origin(
            d.pop("connect_export_origin", UNSET)
        )

        _cost_code = d.pop("cost_code", UNSET)
        cost_code: ListRfisResponse200ItemCostCode | Unset
        if isinstance(_cost_code, Unset):
            cost_code = UNSET
        else:
            cost_code = ListRfisResponse200ItemCostCode.from_dict(_cost_code)

        _cost_impact = d.pop("cost_impact", UNSET)
        cost_impact: ListRfisResponse200ItemCostImpact | Unset
        if isinstance(_cost_impact, Unset):
            cost_impact = UNSET
        else:
            cost_impact = ListRfisResponse200ItemCostImpact.from_dict(_cost_impact)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _created_by = d.pop("created_by", UNSET)
        created_by: ListRfisResponse200ItemCreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = ListRfisResponse200ItemCreatedBy.from_dict(_created_by)

        current_revision = d.pop("current_revision", UNSET)

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: ListRfisResponse200ItemCustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = ListRfisResponse200ItemCustomFields.from_dict(
                _custom_fields
            )

        deleted = d.pop("deleted", UNSET)

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        def _parse_due_date(data: object) -> datetime.date | datetime.datetime | Unset:
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                due_date_type_0 = datetime.date.fromisoformat(data)

                return due_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            if not isinstance(data, str):
                raise TypeError()
            due_date_type_1 = datetime.datetime.fromisoformat(data)

            return due_date_type_1

        due_date = _parse_due_date(d.pop("due_date", UNSET))

        full_number = d.pop("full_number", UNSET)

        has_revisions = d.pop("has_revisions", UNSET)

        id = d.pop("id", UNSET)

        _initiated_at = d.pop("initiated_at", UNSET)
        initiated_at: datetime.datetime | Unset
        if isinstance(_initiated_at, Unset):
            initiated_at = UNSET
        else:
            initiated_at = datetime.datetime.fromisoformat(_initiated_at)

        link = d.pop("link", UNSET)

        _location = d.pop("location", UNSET)
        location: ListRfisResponse200ItemLocation | Unset
        if isinstance(_location, Unset):
            location = UNSET
        else:
            location = ListRfisResponse200ItemLocation.from_dict(_location)

        location_id = d.pop("location_id", UNSET)

        number = d.pop("number", UNSET)

        prefix = d.pop("prefix", UNSET)

        private = d.pop("private", UNSET)

        _project_stage = d.pop("project_stage", UNSET)
        project_stage: ListRfisResponse200ItemProjectStage | Unset
        if isinstance(_project_stage, Unset):
            project_stage = UNSET
        else:
            project_stage = ListRfisResponse200ItemProjectStage.from_dict(
                _project_stage
            )

        _questions = d.pop("questions", UNSET)
        questions: list[ListRfisResponse200ItemQuestionsItem] | Unset = UNSET
        if _questions is not UNSET:
            questions = []
            for questions_item_data in _questions:
                questions_item = ListRfisResponse200ItemQuestionsItem.from_dict(
                    questions_item_data
                )

                questions.append(questions_item)

        _received_from = d.pop("received_from", UNSET)
        received_from: ListRfisResponse200ItemReceivedFrom | Unset
        if isinstance(_received_from, Unset):
            received_from = UNSET
        else:
            received_from = ListRfisResponse200ItemReceivedFrom.from_dict(
                _received_from
            )

        reference = d.pop("reference", UNSET)

        _responsible_contractor = d.pop("responsible_contractor", UNSET)
        responsible_contractor: ListRfisResponse200ItemResponsibleContractor | Unset
        if isinstance(_responsible_contractor, Unset):
            responsible_contractor = UNSET
        else:
            responsible_contractor = (
                ListRfisResponse200ItemResponsibleContractor.from_dict(
                    _responsible_contractor
                )
            )

        revision = d.pop("revision", UNSET)

        _rfi_manager = d.pop("rfi_manager", UNSET)
        rfi_manager: ListRfisResponse200ItemRfiManager | Unset
        if isinstance(_rfi_manager, Unset):
            rfi_manager = UNSET
        else:
            rfi_manager = ListRfisResponse200ItemRfiManager.from_dict(_rfi_manager)

        _schedule_impact = d.pop("schedule_impact", UNSET)
        schedule_impact: ListRfisResponse200ItemScheduleImpact | Unset
        if isinstance(_schedule_impact, Unset):
            schedule_impact = UNSET
        else:
            schedule_impact = ListRfisResponse200ItemScheduleImpact.from_dict(
                _schedule_impact
            )

        source_rfi_header_id = d.pop("source_rfi_header_id", UNSET)

        specification_section_id = d.pop("specification_section_id", UNSET)

        _status = d.pop("status", UNSET)
        status: ListRfisResponse200ItemStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ListRfisResponse200ItemStatus(_status)

        _sub_job = d.pop("sub_job", UNSET)
        sub_job: ListRfisResponse200ItemSubJob | Unset
        if isinstance(_sub_job, Unset):
            sub_job = UNSET
        else:
            sub_job = ListRfisResponse200ItemSubJob.from_dict(_sub_job)

        subject = d.pop("subject", UNSET)

        _time_resolved = d.pop("time_resolved", UNSET)
        time_resolved: datetime.datetime | Unset
        if isinstance(_time_resolved, Unset):
            time_resolved = UNSET
        else:
            time_resolved = datetime.datetime.fromisoformat(_time_resolved)

        translated_status = d.pop("translated_status", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_rfis_response_200_item = cls(
            assignee=assignee,
            assignees=assignees,
            ball_in_court=ball_in_court,
            ball_in_courts=ball_in_courts,
            connect_export_origin=connect_export_origin,
            cost_code=cost_code,
            cost_impact=cost_impact,
            created_at=created_at,
            created_by=created_by,
            current_revision=current_revision,
            custom_fields=custom_fields,
            deleted=deleted,
            deleted_at=deleted_at,
            due_date=due_date,
            full_number=full_number,
            has_revisions=has_revisions,
            id=id,
            initiated_at=initiated_at,
            link=link,
            location=location,
            location_id=location_id,
            number=number,
            prefix=prefix,
            private=private,
            project_stage=project_stage,
            questions=questions,
            received_from=received_from,
            reference=reference,
            responsible_contractor=responsible_contractor,
            revision=revision,
            rfi_manager=rfi_manager,
            schedule_impact=schedule_impact,
            source_rfi_header_id=source_rfi_header_id,
            specification_section_id=specification_section_id,
            status=status,
            sub_job=sub_job,
            subject=subject,
            time_resolved=time_resolved,
            translated_status=translated_status,
            updated_at=updated_at,
        )

        list_rfis_response_200_item.additional_properties = d
        return list_rfis_response_200_item

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
