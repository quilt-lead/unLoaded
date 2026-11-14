from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_rfi_response_201_status import CreateRfiResponse201Status
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_rfi_response_201_assignee import CreateRfiResponse201Assignee
    from ..models.create_rfi_response_201_assignees_item import (
        CreateRfiResponse201AssigneesItem,
    )
    from ..models.create_rfi_response_201_ball_in_court import (
        CreateRfiResponse201BallInCourt,
    )
    from ..models.create_rfi_response_201_ball_in_courts_item import (
        CreateRfiResponse201BallInCourtsItem,
    )
    from ..models.create_rfi_response_201_connect_export_origin_type_0 import (
        CreateRfiResponse201ConnectExportOriginType0,
    )
    from ..models.create_rfi_response_201_cost_code_type_0 import (
        CreateRfiResponse201CostCodeType0,
    )
    from ..models.create_rfi_response_201_cost_impact_type_0 import (
        CreateRfiResponse201CostImpactType0,
    )
    from ..models.create_rfi_response_201_created_by import (
        CreateRfiResponse201CreatedBy,
    )
    from ..models.create_rfi_response_201_custom_fields import (
        CreateRfiResponse201CustomFields,
    )
    from ..models.create_rfi_response_201_custom_textfield_1_type_0 import (
        CreateRfiResponse201CustomTextfield1Type0,
    )
    from ..models.create_rfi_response_201_custom_textfield_2_type_0 import (
        CreateRfiResponse201CustomTextfield2Type0,
    )
    from ..models.create_rfi_response_201_distribution_list_item import (
        CreateRfiResponse201DistributionListItem,
    )
    from ..models.create_rfi_response_201_location_type_0 import (
        CreateRfiResponse201LocationType0,
    )
    from ..models.create_rfi_response_201_questions_item import (
        CreateRfiResponse201QuestionsItem,
    )
    from ..models.create_rfi_response_201_received_from import (
        CreateRfiResponse201ReceivedFrom,
    )
    from ..models.create_rfi_response_201_responsible_contractor_type_0 import (
        CreateRfiResponse201ResponsibleContractorType0,
    )
    from ..models.create_rfi_response_201_rfi_manager import (
        CreateRfiResponse201RfiManager,
    )
    from ..models.create_rfi_response_201_schedule_impact_type_0 import (
        CreateRfiResponse201ScheduleImpactType0,
    )
    from ..models.create_rfi_response_201_specification_section_type_0 import (
        CreateRfiResponse201SpecificationSectionType0,
    )


T = TypeVar("T", bound="CreateRfiResponse201")


@_attrs_define
class CreateRfiResponse201:
    """
    Attributes:
        accepted (bool | Unset): RFI Acceptance status, true means the RFI is accepted and closed
        assignee (CreateRfiResponse201Assignee | Unset):
        assignees (list[CreateRfiResponse201AssigneesItem] | Unset): RFI Assignees
        ball_in_court (CreateRfiResponse201BallInCourt | Unset):
        ball_in_court_role (str | Unset): Ball in Court Role (can be Assignees, Creator, or RFI Manager)
        ball_in_courts (list[CreateRfiResponse201BallInCourtsItem] | Unset): Ball In Courts
        connect_export_origin (CreateRfiResponse201ConnectExportOriginType0 | None | Unset): Export origin information
            for RFIs received via cross-account collaboration. Null for RFIs not received via export.
        connect_exported_project_ids (list[int] | Unset): IDs of connected projects to which this RFI has already been
            exported. Use this list with connected project permissions to identify prior export destinations and avoid
            offering duplicate export targets.
        cost_code (CreateRfiResponse201CostCodeType0 | None | Unset):
        cost_impact (CreateRfiResponse201CostImpactType0 | None | Unset):
        created_at (datetime.datetime | Unset): Date created
        created_by (CreateRfiResponse201CreatedBy | Unset): User who created the RFI.
        current_revision (bool | Unset): Designate whether or not this RFI is the latest revision
        custom_fields (CreateRfiResponse201CustomFields | Unset):
        custom_textfield_1 (CreateRfiResponse201CustomTextfield1Type0 | None | Unset): Custom RFI text field 1
        custom_textfield_2 (CreateRfiResponse201CustomTextfield2Type0 | None | Unset): Custom RFI text field 2
        deleted (bool | Unset): Deleted status (this is only shown on deleted records)
        deleted_at (datetime.datetime | Unset): Time deleted (this is only shown on deleted records)
        distribution_list (list[CreateRfiResponse201DistributionListItem] | Unset): RFI Distribution List of Users
        draft (bool | Unset): Draft status, true if draft
        drawing_ids (list[int] | Unset): Array of IDs for associated Drawings
        drawing_number (None | str | Unset): Drawing Number
        due_date (datetime.date | Unset): Due Date
        full_number (str | Unset): Full Number
        has_revisions (bool | Unset): Designate whether or not this RFI has other revisions
        id (int | Unset): ID
        initiated_at (datetime.datetime | Unset): Date initiated
        location (CreateRfiResponse201LocationType0 | None | Unset):
        number (str | Unset): Number
        prefix (None | str | Unset): Prefix
        private (bool | Unset): Private Status
        questions (list[CreateRfiResponse201QuestionsItem] | Unset): List of questions
        received_from (CreateRfiResponse201ReceivedFrom | Unset):
        reference (None | str | Unset): Reference
        responsible_contractor (CreateRfiResponse201ResponsibleContractorType0 | None | Unset):
        revision (str | Unset): Revision Number
        rfi_manager (CreateRfiResponse201RfiManager | Unset):
        schedule_impact (CreateRfiResponse201ScheduleImpactType0 | None | Unset):
        source_rfi_header_id (int | Unset): The ID of The Root RFI Revision
        specification_section (CreateRfiResponse201SpecificationSectionType0 | None | Unset):
        status (CreateRfiResponse201Status | Unset): Status
        subject (str | Unset): Subject
        time_resolved (datetime.datetime | None | Unset): Time RFI was closed
        translated_status (str | Unset): Translated RFI status
        updated_at (datetime.datetime | Unset): Updated at
    """

    accepted: bool | Unset = UNSET
    assignee: CreateRfiResponse201Assignee | Unset = UNSET
    assignees: list[CreateRfiResponse201AssigneesItem] | Unset = UNSET
    ball_in_court: CreateRfiResponse201BallInCourt | Unset = UNSET
    ball_in_court_role: str | Unset = UNSET
    ball_in_courts: list[CreateRfiResponse201BallInCourtsItem] | Unset = UNSET
    connect_export_origin: (
        CreateRfiResponse201ConnectExportOriginType0 | None | Unset
    ) = UNSET
    connect_exported_project_ids: list[int] | Unset = UNSET
    cost_code: CreateRfiResponse201CostCodeType0 | None | Unset = UNSET
    cost_impact: CreateRfiResponse201CostImpactType0 | None | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: CreateRfiResponse201CreatedBy | Unset = UNSET
    current_revision: bool | Unset = UNSET
    custom_fields: CreateRfiResponse201CustomFields | Unset = UNSET
    custom_textfield_1: CreateRfiResponse201CustomTextfield1Type0 | None | Unset = UNSET
    custom_textfield_2: CreateRfiResponse201CustomTextfield2Type0 | None | Unset = UNSET
    deleted: bool | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    distribution_list: list[CreateRfiResponse201DistributionListItem] | Unset = UNSET
    draft: bool | Unset = UNSET
    drawing_ids: list[int] | Unset = UNSET
    drawing_number: None | str | Unset = UNSET
    due_date: datetime.date | Unset = UNSET
    full_number: str | Unset = UNSET
    has_revisions: bool | Unset = UNSET
    id: int | Unset = UNSET
    initiated_at: datetime.datetime | Unset = UNSET
    location: CreateRfiResponse201LocationType0 | None | Unset = UNSET
    number: str | Unset = UNSET
    prefix: None | str | Unset = UNSET
    private: bool | Unset = UNSET
    questions: list[CreateRfiResponse201QuestionsItem] | Unset = UNSET
    received_from: CreateRfiResponse201ReceivedFrom | Unset = UNSET
    reference: None | str | Unset = UNSET
    responsible_contractor: (
        CreateRfiResponse201ResponsibleContractorType0 | None | Unset
    ) = UNSET
    revision: str | Unset = UNSET
    rfi_manager: CreateRfiResponse201RfiManager | Unset = UNSET
    schedule_impact: CreateRfiResponse201ScheduleImpactType0 | None | Unset = UNSET
    source_rfi_header_id: int | Unset = UNSET
    specification_section: (
        CreateRfiResponse201SpecificationSectionType0 | None | Unset
    ) = UNSET
    status: CreateRfiResponse201Status | Unset = UNSET
    subject: str | Unset = UNSET
    time_resolved: datetime.datetime | None | Unset = UNSET
    translated_status: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_rfi_response_201_connect_export_origin_type_0 import (
            CreateRfiResponse201ConnectExportOriginType0,
        )
        from ..models.create_rfi_response_201_cost_code_type_0 import (
            CreateRfiResponse201CostCodeType0,
        )
        from ..models.create_rfi_response_201_cost_impact_type_0 import (
            CreateRfiResponse201CostImpactType0,
        )
        from ..models.create_rfi_response_201_custom_textfield_1_type_0 import (
            CreateRfiResponse201CustomTextfield1Type0,
        )
        from ..models.create_rfi_response_201_custom_textfield_2_type_0 import (
            CreateRfiResponse201CustomTextfield2Type0,
        )
        from ..models.create_rfi_response_201_location_type_0 import (
            CreateRfiResponse201LocationType0,
        )
        from ..models.create_rfi_response_201_responsible_contractor_type_0 import (
            CreateRfiResponse201ResponsibleContractorType0,
        )
        from ..models.create_rfi_response_201_schedule_impact_type_0 import (
            CreateRfiResponse201ScheduleImpactType0,
        )
        from ..models.create_rfi_response_201_specification_section_type_0 import (
            CreateRfiResponse201SpecificationSectionType0,
        )

        accepted = self.accepted

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

        ball_in_court_role = self.ball_in_court_role

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
            self.connect_export_origin, CreateRfiResponse201ConnectExportOriginType0
        ):
            connect_export_origin = self.connect_export_origin.to_dict()
        else:
            connect_export_origin = self.connect_export_origin

        connect_exported_project_ids: list[int] | Unset = UNSET
        if not isinstance(self.connect_exported_project_ids, Unset):
            connect_exported_project_ids = self.connect_exported_project_ids

        cost_code: dict[str, Any] | None | Unset
        if isinstance(self.cost_code, Unset):
            cost_code = UNSET
        elif isinstance(self.cost_code, CreateRfiResponse201CostCodeType0):
            cost_code = self.cost_code.to_dict()
        else:
            cost_code = self.cost_code

        cost_impact: dict[str, Any] | None | Unset
        if isinstance(self.cost_impact, Unset):
            cost_impact = UNSET
        elif isinstance(self.cost_impact, CreateRfiResponse201CostImpactType0):
            cost_impact = self.cost_impact.to_dict()
        else:
            cost_impact = self.cost_impact

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

        custom_textfield_1: dict[str, Any] | None | Unset
        if isinstance(self.custom_textfield_1, Unset):
            custom_textfield_1 = UNSET
        elif isinstance(
            self.custom_textfield_1, CreateRfiResponse201CustomTextfield1Type0
        ):
            custom_textfield_1 = self.custom_textfield_1.to_dict()
        else:
            custom_textfield_1 = self.custom_textfield_1

        custom_textfield_2: dict[str, Any] | None | Unset
        if isinstance(self.custom_textfield_2, Unset):
            custom_textfield_2 = UNSET
        elif isinstance(
            self.custom_textfield_2, CreateRfiResponse201CustomTextfield2Type0
        ):
            custom_textfield_2 = self.custom_textfield_2.to_dict()
        else:
            custom_textfield_2 = self.custom_textfield_2

        deleted = self.deleted

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        distribution_list: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distribution_list, Unset):
            distribution_list = []
            for distribution_list_item_data in self.distribution_list:
                distribution_list_item = distribution_list_item_data.to_dict()
                distribution_list.append(distribution_list_item)

        draft = self.draft

        drawing_ids: list[int] | Unset = UNSET
        if not isinstance(self.drawing_ids, Unset):
            drawing_ids = self.drawing_ids

        drawing_number: None | str | Unset
        if isinstance(self.drawing_number, Unset):
            drawing_number = UNSET
        else:
            drawing_number = self.drawing_number

        due_date: str | Unset = UNSET
        if not isinstance(self.due_date, Unset):
            due_date = self.due_date.isoformat()

        full_number = self.full_number

        has_revisions = self.has_revisions

        id = self.id

        initiated_at: str | Unset = UNSET
        if not isinstance(self.initiated_at, Unset):
            initiated_at = self.initiated_at.isoformat()

        location: dict[str, Any] | None | Unset
        if isinstance(self.location, Unset):
            location = UNSET
        elif isinstance(self.location, CreateRfiResponse201LocationType0):
            location = self.location.to_dict()
        else:
            location = self.location

        number = self.number

        prefix: None | str | Unset
        if isinstance(self.prefix, Unset):
            prefix = UNSET
        else:
            prefix = self.prefix

        private = self.private

        questions: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.questions, Unset):
            questions = []
            for questions_item_data in self.questions:
                questions_item = questions_item_data.to_dict()
                questions.append(questions_item)

        received_from: dict[str, Any] | Unset = UNSET
        if not isinstance(self.received_from, Unset):
            received_from = self.received_from.to_dict()

        reference: None | str | Unset
        if isinstance(self.reference, Unset):
            reference = UNSET
        else:
            reference = self.reference

        responsible_contractor: dict[str, Any] | None | Unset
        if isinstance(self.responsible_contractor, Unset):
            responsible_contractor = UNSET
        elif isinstance(
            self.responsible_contractor, CreateRfiResponse201ResponsibleContractorType0
        ):
            responsible_contractor = self.responsible_contractor.to_dict()
        else:
            responsible_contractor = self.responsible_contractor

        revision = self.revision

        rfi_manager: dict[str, Any] | Unset = UNSET
        if not isinstance(self.rfi_manager, Unset):
            rfi_manager = self.rfi_manager.to_dict()

        schedule_impact: dict[str, Any] | None | Unset
        if isinstance(self.schedule_impact, Unset):
            schedule_impact = UNSET
        elif isinstance(self.schedule_impact, CreateRfiResponse201ScheduleImpactType0):
            schedule_impact = self.schedule_impact.to_dict()
        else:
            schedule_impact = self.schedule_impact

        source_rfi_header_id = self.source_rfi_header_id

        specification_section: dict[str, Any] | None | Unset
        if isinstance(self.specification_section, Unset):
            specification_section = UNSET
        elif isinstance(
            self.specification_section, CreateRfiResponse201SpecificationSectionType0
        ):
            specification_section = self.specification_section.to_dict()
        else:
            specification_section = self.specification_section

        status: str | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.value

        subject = self.subject

        time_resolved: None | str | Unset
        if isinstance(self.time_resolved, Unset):
            time_resolved = UNSET
        elif isinstance(self.time_resolved, datetime.datetime):
            time_resolved = self.time_resolved.isoformat()
        else:
            time_resolved = self.time_resolved

        translated_status = self.translated_status

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if accepted is not UNSET:
            field_dict["accepted"] = accepted
        if assignee is not UNSET:
            field_dict["assignee"] = assignee
        if assignees is not UNSET:
            field_dict["assignees"] = assignees
        if ball_in_court is not UNSET:
            field_dict["ball_in_court"] = ball_in_court
        if ball_in_court_role is not UNSET:
            field_dict["ball_in_court_role"] = ball_in_court_role
        if ball_in_courts is not UNSET:
            field_dict["ball_in_courts"] = ball_in_courts
        if connect_export_origin is not UNSET:
            field_dict["connect_export_origin"] = connect_export_origin
        if connect_exported_project_ids is not UNSET:
            field_dict["connect_exported_project_ids"] = connect_exported_project_ids
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
        if custom_textfield_1 is not UNSET:
            field_dict["custom_textfield_1"] = custom_textfield_1
        if custom_textfield_2 is not UNSET:
            field_dict["custom_textfield_2"] = custom_textfield_2
        if deleted is not UNSET:
            field_dict["deleted"] = deleted
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if distribution_list is not UNSET:
            field_dict["distribution_list"] = distribution_list
        if draft is not UNSET:
            field_dict["draft"] = draft
        if drawing_ids is not UNSET:
            field_dict["drawing_ids"] = drawing_ids
        if drawing_number is not UNSET:
            field_dict["drawing_number"] = drawing_number
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
        if location is not UNSET:
            field_dict["location"] = location
        if number is not UNSET:
            field_dict["number"] = number
        if prefix is not UNSET:
            field_dict["prefix"] = prefix
        if private is not UNSET:
            field_dict["private"] = private
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
        if specification_section is not UNSET:
            field_dict["specification_section"] = specification_section
        if status is not UNSET:
            field_dict["status"] = status
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
        from ..models.create_rfi_response_201_assignee import (
            CreateRfiResponse201Assignee,
        )
        from ..models.create_rfi_response_201_assignees_item import (
            CreateRfiResponse201AssigneesItem,
        )
        from ..models.create_rfi_response_201_ball_in_court import (
            CreateRfiResponse201BallInCourt,
        )
        from ..models.create_rfi_response_201_ball_in_courts_item import (
            CreateRfiResponse201BallInCourtsItem,
        )
        from ..models.create_rfi_response_201_connect_export_origin_type_0 import (
            CreateRfiResponse201ConnectExportOriginType0,
        )
        from ..models.create_rfi_response_201_cost_code_type_0 import (
            CreateRfiResponse201CostCodeType0,
        )
        from ..models.create_rfi_response_201_cost_impact_type_0 import (
            CreateRfiResponse201CostImpactType0,
        )
        from ..models.create_rfi_response_201_created_by import (
            CreateRfiResponse201CreatedBy,
        )
        from ..models.create_rfi_response_201_custom_fields import (
            CreateRfiResponse201CustomFields,
        )
        from ..models.create_rfi_response_201_custom_textfield_1_type_0 import (
            CreateRfiResponse201CustomTextfield1Type0,
        )
        from ..models.create_rfi_response_201_custom_textfield_2_type_0 import (
            CreateRfiResponse201CustomTextfield2Type0,
        )
        from ..models.create_rfi_response_201_distribution_list_item import (
            CreateRfiResponse201DistributionListItem,
        )
        from ..models.create_rfi_response_201_location_type_0 import (
            CreateRfiResponse201LocationType0,
        )
        from ..models.create_rfi_response_201_questions_item import (
            CreateRfiResponse201QuestionsItem,
        )
        from ..models.create_rfi_response_201_received_from import (
            CreateRfiResponse201ReceivedFrom,
        )
        from ..models.create_rfi_response_201_responsible_contractor_type_0 import (
            CreateRfiResponse201ResponsibleContractorType0,
        )
        from ..models.create_rfi_response_201_rfi_manager import (
            CreateRfiResponse201RfiManager,
        )
        from ..models.create_rfi_response_201_schedule_impact_type_0 import (
            CreateRfiResponse201ScheduleImpactType0,
        )
        from ..models.create_rfi_response_201_specification_section_type_0 import (
            CreateRfiResponse201SpecificationSectionType0,
        )

        d = dict(src_dict)
        accepted = d.pop("accepted", UNSET)

        _assignee = d.pop("assignee", UNSET)
        assignee: CreateRfiResponse201Assignee | Unset
        if isinstance(_assignee, Unset):
            assignee = UNSET
        else:
            assignee = CreateRfiResponse201Assignee.from_dict(_assignee)

        _assignees = d.pop("assignees", UNSET)
        assignees: list[CreateRfiResponse201AssigneesItem] | Unset = UNSET
        if _assignees is not UNSET:
            assignees = []
            for assignees_item_data in _assignees:
                assignees_item = CreateRfiResponse201AssigneesItem.from_dict(
                    assignees_item_data
                )

                assignees.append(assignees_item)

        _ball_in_court = d.pop("ball_in_court", UNSET)
        ball_in_court: CreateRfiResponse201BallInCourt | Unset
        if isinstance(_ball_in_court, Unset):
            ball_in_court = UNSET
        else:
            ball_in_court = CreateRfiResponse201BallInCourt.from_dict(_ball_in_court)

        ball_in_court_role = d.pop("ball_in_court_role", UNSET)

        _ball_in_courts = d.pop("ball_in_courts", UNSET)
        ball_in_courts: list[CreateRfiResponse201BallInCourtsItem] | Unset = UNSET
        if _ball_in_courts is not UNSET:
            ball_in_courts = []
            for ball_in_courts_item_data in _ball_in_courts:
                ball_in_courts_item = CreateRfiResponse201BallInCourtsItem.from_dict(
                    ball_in_courts_item_data
                )

                ball_in_courts.append(ball_in_courts_item)

        def _parse_connect_export_origin(
            data: object,
        ) -> CreateRfiResponse201ConnectExportOriginType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                connect_export_origin_type_0 = (
                    CreateRfiResponse201ConnectExportOriginType0.from_dict(data)
                )

                return connect_export_origin_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateRfiResponse201ConnectExportOriginType0 | None | Unset, data
            )

        connect_export_origin = _parse_connect_export_origin(
            d.pop("connect_export_origin", UNSET)
        )

        connect_exported_project_ids = cast(
            list[int], d.pop("connect_exported_project_ids", UNSET)
        )

        def _parse_cost_code(
            data: object,
        ) -> CreateRfiResponse201CostCodeType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                cost_code_type_0 = CreateRfiResponse201CostCodeType0.from_dict(data)

                return cost_code_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201CostCodeType0 | None | Unset, data)

        cost_code = _parse_cost_code(d.pop("cost_code", UNSET))

        def _parse_cost_impact(
            data: object,
        ) -> CreateRfiResponse201CostImpactType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                cost_impact_type_0 = CreateRfiResponse201CostImpactType0.from_dict(data)

                return cost_impact_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201CostImpactType0 | None | Unset, data)

        cost_impact = _parse_cost_impact(d.pop("cost_impact", UNSET))

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _created_by = d.pop("created_by", UNSET)
        created_by: CreateRfiResponse201CreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = CreateRfiResponse201CreatedBy.from_dict(_created_by)

        current_revision = d.pop("current_revision", UNSET)

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: CreateRfiResponse201CustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = CreateRfiResponse201CustomFields.from_dict(_custom_fields)

        def _parse_custom_textfield_1(
            data: object,
        ) -> CreateRfiResponse201CustomTextfield1Type0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                custom_textfield_1_type_0 = (
                    CreateRfiResponse201CustomTextfield1Type0.from_dict(data)
                )

                return custom_textfield_1_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201CustomTextfield1Type0 | None | Unset, data)

        custom_textfield_1 = _parse_custom_textfield_1(
            d.pop("custom_textfield_1", UNSET)
        )

        def _parse_custom_textfield_2(
            data: object,
        ) -> CreateRfiResponse201CustomTextfield2Type0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                custom_textfield_2_type_0 = (
                    CreateRfiResponse201CustomTextfield2Type0.from_dict(data)
                )

                return custom_textfield_2_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201CustomTextfield2Type0 | None | Unset, data)

        custom_textfield_2 = _parse_custom_textfield_2(
            d.pop("custom_textfield_2", UNSET)
        )

        deleted = d.pop("deleted", UNSET)

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        _distribution_list = d.pop("distribution_list", UNSET)
        distribution_list: list[CreateRfiResponse201DistributionListItem] | Unset = (
            UNSET
        )
        if _distribution_list is not UNSET:
            distribution_list = []
            for distribution_list_item_data in _distribution_list:
                distribution_list_item = (
                    CreateRfiResponse201DistributionListItem.from_dict(
                        distribution_list_item_data
                    )
                )

                distribution_list.append(distribution_list_item)

        draft = d.pop("draft", UNSET)

        drawing_ids = cast(list[int], d.pop("drawing_ids", UNSET))

        def _parse_drawing_number(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        drawing_number = _parse_drawing_number(d.pop("drawing_number", UNSET))

        _due_date = d.pop("due_date", UNSET)
        due_date: datetime.date | Unset
        if isinstance(_due_date, Unset):
            due_date = UNSET
        else:
            due_date = datetime.date.fromisoformat(_due_date)

        full_number = d.pop("full_number", UNSET)

        has_revisions = d.pop("has_revisions", UNSET)

        id = d.pop("id", UNSET)

        _initiated_at = d.pop("initiated_at", UNSET)
        initiated_at: datetime.datetime | Unset
        if isinstance(_initiated_at, Unset):
            initiated_at = UNSET
        else:
            initiated_at = datetime.datetime.fromisoformat(_initiated_at)

        def _parse_location(
            data: object,
        ) -> CreateRfiResponse201LocationType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                location_type_0 = CreateRfiResponse201LocationType0.from_dict(data)

                return location_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201LocationType0 | None | Unset, data)

        location = _parse_location(d.pop("location", UNSET))

        number = d.pop("number", UNSET)

        def _parse_prefix(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        prefix = _parse_prefix(d.pop("prefix", UNSET))

        private = d.pop("private", UNSET)

        _questions = d.pop("questions", UNSET)
        questions: list[CreateRfiResponse201QuestionsItem] | Unset = UNSET
        if _questions is not UNSET:
            questions = []
            for questions_item_data in _questions:
                questions_item = CreateRfiResponse201QuestionsItem.from_dict(
                    questions_item_data
                )

                questions.append(questions_item)

        _received_from = d.pop("received_from", UNSET)
        received_from: CreateRfiResponse201ReceivedFrom | Unset
        if isinstance(_received_from, Unset):
            received_from = UNSET
        else:
            received_from = CreateRfiResponse201ReceivedFrom.from_dict(_received_from)

        def _parse_reference(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        reference = _parse_reference(d.pop("reference", UNSET))

        def _parse_responsible_contractor(
            data: object,
        ) -> CreateRfiResponse201ResponsibleContractorType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                responsible_contractor_type_0 = (
                    CreateRfiResponse201ResponsibleContractorType0.from_dict(data)
                )

                return responsible_contractor_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateRfiResponse201ResponsibleContractorType0 | None | Unset, data
            )

        responsible_contractor = _parse_responsible_contractor(
            d.pop("responsible_contractor", UNSET)
        )

        revision = d.pop("revision", UNSET)

        _rfi_manager = d.pop("rfi_manager", UNSET)
        rfi_manager: CreateRfiResponse201RfiManager | Unset
        if isinstance(_rfi_manager, Unset):
            rfi_manager = UNSET
        else:
            rfi_manager = CreateRfiResponse201RfiManager.from_dict(_rfi_manager)

        def _parse_schedule_impact(
            data: object,
        ) -> CreateRfiResponse201ScheduleImpactType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                schedule_impact_type_0 = (
                    CreateRfiResponse201ScheduleImpactType0.from_dict(data)
                )

                return schedule_impact_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateRfiResponse201ScheduleImpactType0 | None | Unset, data)

        schedule_impact = _parse_schedule_impact(d.pop("schedule_impact", UNSET))

        source_rfi_header_id = d.pop("source_rfi_header_id", UNSET)

        def _parse_specification_section(
            data: object,
        ) -> CreateRfiResponse201SpecificationSectionType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                specification_section_type_0 = (
                    CreateRfiResponse201SpecificationSectionType0.from_dict(data)
                )

                return specification_section_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateRfiResponse201SpecificationSectionType0 | None | Unset, data
            )

        specification_section = _parse_specification_section(
            d.pop("specification_section", UNSET)
        )

        _status = d.pop("status", UNSET)
        status: CreateRfiResponse201Status | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = CreateRfiResponse201Status(_status)

        subject = d.pop("subject", UNSET)

        def _parse_time_resolved(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                time_resolved_type_0 = datetime.datetime.fromisoformat(data)

                return time_resolved_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        time_resolved = _parse_time_resolved(d.pop("time_resolved", UNSET))

        translated_status = d.pop("translated_status", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        create_rfi_response_201 = cls(
            accepted=accepted,
            assignee=assignee,
            assignees=assignees,
            ball_in_court=ball_in_court,
            ball_in_court_role=ball_in_court_role,
            ball_in_courts=ball_in_courts,
            connect_export_origin=connect_export_origin,
            connect_exported_project_ids=connect_exported_project_ids,
            cost_code=cost_code,
            cost_impact=cost_impact,
            created_at=created_at,
            created_by=created_by,
            current_revision=current_revision,
            custom_fields=custom_fields,
            custom_textfield_1=custom_textfield_1,
            custom_textfield_2=custom_textfield_2,
            deleted=deleted,
            deleted_at=deleted_at,
            distribution_list=distribution_list,
            draft=draft,
            drawing_ids=drawing_ids,
            drawing_number=drawing_number,
            due_date=due_date,
            full_number=full_number,
            has_revisions=has_revisions,
            id=id,
            initiated_at=initiated_at,
            location=location,
            number=number,
            prefix=prefix,
            private=private,
            questions=questions,
            received_from=received_from,
            reference=reference,
            responsible_contractor=responsible_contractor,
            revision=revision,
            rfi_manager=rfi_manager,
            schedule_impact=schedule_impact,
            source_rfi_header_id=source_rfi_header_id,
            specification_section=specification_section,
            status=status,
            subject=subject,
            time_resolved=time_resolved,
            translated_status=translated_status,
            updated_at=updated_at,
        )

        create_rfi_response_201.additional_properties = d
        return create_rfi_response_201

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
