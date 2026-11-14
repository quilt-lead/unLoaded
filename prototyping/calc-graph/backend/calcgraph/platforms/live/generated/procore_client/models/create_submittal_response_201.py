from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_submittal_response_201_approvers_item import (
        CreateSubmittalResponse201ApproversItem,
    )
    from ..models.create_submittal_response_201_attachments_item import (
        CreateSubmittalResponse201AttachmentsItem,
    )
    from ..models.create_submittal_response_201_ball_in_court_item import (
        CreateSubmittalResponse201BallInCourtItem,
    )
    from ..models.create_submittal_response_201_cost_code_type_0 import (
        CreateSubmittalResponse201CostCodeType0,
    )
    from ..models.create_submittal_response_201_created_by import (
        CreateSubmittalResponse201CreatedBy,
    )
    from ..models.create_submittal_response_201_custom_fields import (
        CreateSubmittalResponse201CustomFields,
    )
    from ..models.create_submittal_response_201_distributed_submittals_item import (
        CreateSubmittalResponse201DistributedSubmittalsItem,
    )
    from ..models.create_submittal_response_201_distribution_members_item import (
        CreateSubmittalResponse201DistributionMembersItem,
    )
    from ..models.create_submittal_response_201_location_type_0 import (
        CreateSubmittalResponse201LocationType0,
    )
    from ..models.create_submittal_response_201_operation_item_errors_item import (
        CreateSubmittalResponse201OperationItemErrorsItem,
    )
    from ..models.create_submittal_response_201_received_from_type_0 import (
        CreateSubmittalResponse201ReceivedFromType0,
    )
    from ..models.create_submittal_response_201_responsible_contractor_type_0 import (
        CreateSubmittalResponse201ResponsibleContractorType0,
    )
    from ..models.create_submittal_response_201_scheduled_task_type_0 import (
        CreateSubmittalResponse201ScheduledTaskType0,
    )
    from ..models.create_submittal_response_201_specification_section import (
        CreateSubmittalResponse201SpecificationSection,
    )
    from ..models.create_submittal_response_201_status import (
        CreateSubmittalResponse201Status,
    )
    from ..models.create_submittal_response_201_sub_job_type_0 import (
        CreateSubmittalResponse201SubJobType0,
    )
    from ..models.create_submittal_response_201_submittal_manager import (
        CreateSubmittalResponse201SubmittalManager,
    )
    from ..models.create_submittal_response_201_submittal_package import (
        CreateSubmittalResponse201SubmittalPackage,
    )
    from ..models.create_submittal_response_201_submittal_workflow_template_type_0 import (
        CreateSubmittalResponse201SubmittalWorkflowTemplateType0,
    )
    from ..models.create_submittal_response_201_type import (
        CreateSubmittalResponse201Type,
    )


T = TypeVar("T", bound="CreateSubmittalResponse201")


@_attrs_define
class CreateSubmittalResponse201:
    """Includes all fields, detailed approver info, distribution history, and custom fields.

    Attributes:
        actual_delivery_date (datetime.date | None | Unset):
        approvers (list[CreateSubmittalResponse201ApproversItem] | Unset):
        attachments (list[CreateSubmittalResponse201AttachmentsItem] | Unset):
        attachments_count (int | Unset): Number of attachments on the submittal.
        ball_in_court (list[CreateSubmittalResponse201BallInCourtItem] | Unset):
        buffer_time (int | None | Unset): Buffer time, in working days, for Dynamic Submittal Plan scheduling.
        closed_at (datetime.datetime | None | Unset): Timestamp when the submittal was closed.
        confirmed_delivery_date (datetime.date | None | Unset):
        cost_code (CreateSubmittalResponse201CostCodeType0 | None | Unset):
        created_at (datetime.datetime | Unset):
        created_by (CreateSubmittalResponse201CreatedBy | Unset):
        current_revision (bool | Unset):
        custom_fields (CreateSubmittalResponse201CustomFields | Unset):
        custom_textarea_1 (None | str | Unset): Value of the project's custom submittal textarea field. Null when unset.
            The field label is configured in Submittals Settings.
        custom_textfield_1 (None | str | Unset): Value of the project's custom submittal text field. Null when unset.
            The field label is configured in Submittals Settings.
        deleted_at (datetime.datetime | Unset): *This field only displays on deleted items
        description (str | Unset):
        design_team_review_time (int | None | Unset):
        distributed_at (datetime.datetime | None | Unset):
        distributed_submittals (list[CreateSubmittalResponse201DistributedSubmittalsItem] | Unset):
        distribution_members (list[CreateSubmittalResponse201DistributionMembersItem] | Unset):
        due_date (datetime.date | None | Unset):
        for_record_only (bool | Unset):
        formatted_number (str | Unset):
        id (int | Unset):
        internal_review_time (int | None | Unset):
        is_rejected (bool | Unset): Whether the submittal was rejected during its approval workflow.
        issue_date (datetime.date | None | Unset):
        lead_time (int | None | Unset):
        location (CreateSubmittalResponse201LocationType0 | None | Unset):
        number (str | Unset):
        open_date (datetime.date | None | Unset):
        operation_item_errors (list[CreateSubmittalResponse201OperationItemErrorsItem] | Unset): Errors recorded for
            this submittal by the most recent bulk/async operation. Empty when the last operation succeeded.
        prepare_time (int | None | Unset): Prepare time, in working days, for Dynamic Submittal Plan scheduling. Null
            when not set.
        private (bool | Unset):
        received_date (datetime.date | None | Unset):
        received_from (CreateSubmittalResponse201ReceivedFromType0 | None | Unset):
        rejected_submittal_log_approver_id (int | None | Unset): ID of the approver whose response rejected the
            submittal. Null when the submittal has not been rejected.
        required_on_site_date (datetime.date | None | Unset):
        responsible_contractor (CreateSubmittalResponse201ResponsibleContractorType0 | None | Unset):
        revision (str | Unset):
        rich_text_description (str | Unset): HTML-formatted (rich text) version of the submittal description.
            Complements the plain-text `description`.
        scheduled_task (CreateSubmittalResponse201ScheduledTaskType0 | None | Unset):
        source_submittal_log_id (int | Unset):
        specification_section (CreateSubmittalResponse201SpecificationSection | Unset):
        status (CreateSubmittalResponse201Status | Unset):
        sub_job (CreateSubmittalResponse201SubJobType0 | None | Unset):
        submit_by (datetime.date | None | Unset):
        submittal_manager (CreateSubmittalResponse201SubmittalManager | Unset):
        submittal_package (CreateSubmittalResponse201SubmittalPackage | Unset):
        submittal_workflow_template (CreateSubmittalResponse201SubmittalWorkflowTemplateType0 | None | Unset): Workflow
            template applied to this submittal, if any. Null when no template has been applied.
        submittal_workflow_template_applied_at (datetime.datetime | None | Unset): Timestamp when a workflow template
            was applied to this submittal, in ISO 8601 format. Null when no template has been applied.
        title (str | Unset):
        type_ (CreateSubmittalResponse201Type | Unset):
        updated_at (datetime.datetime | Unset):
    """

    actual_delivery_date: datetime.date | None | Unset = UNSET
    approvers: list[CreateSubmittalResponse201ApproversItem] | Unset = UNSET
    attachments: list[CreateSubmittalResponse201AttachmentsItem] | Unset = UNSET
    attachments_count: int | Unset = UNSET
    ball_in_court: list[CreateSubmittalResponse201BallInCourtItem] | Unset = UNSET
    buffer_time: int | None | Unset = UNSET
    closed_at: datetime.datetime | None | Unset = UNSET
    confirmed_delivery_date: datetime.date | None | Unset = UNSET
    cost_code: CreateSubmittalResponse201CostCodeType0 | None | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: CreateSubmittalResponse201CreatedBy | Unset = UNSET
    current_revision: bool | Unset = UNSET
    custom_fields: CreateSubmittalResponse201CustomFields | Unset = UNSET
    custom_textarea_1: None | str | Unset = UNSET
    custom_textfield_1: None | str | Unset = UNSET
    deleted_at: datetime.datetime | Unset = UNSET
    description: str | Unset = UNSET
    design_team_review_time: int | None | Unset = UNSET
    distributed_at: datetime.datetime | None | Unset = UNSET
    distributed_submittals: (
        list[CreateSubmittalResponse201DistributedSubmittalsItem] | Unset
    ) = UNSET
    distribution_members: (
        list[CreateSubmittalResponse201DistributionMembersItem] | Unset
    ) = UNSET
    due_date: datetime.date | None | Unset = UNSET
    for_record_only: bool | Unset = UNSET
    formatted_number: str | Unset = UNSET
    id: int | Unset = UNSET
    internal_review_time: int | None | Unset = UNSET
    is_rejected: bool | Unset = UNSET
    issue_date: datetime.date | None | Unset = UNSET
    lead_time: int | None | Unset = UNSET
    location: CreateSubmittalResponse201LocationType0 | None | Unset = UNSET
    number: str | Unset = UNSET
    open_date: datetime.date | None | Unset = UNSET
    operation_item_errors: (
        list[CreateSubmittalResponse201OperationItemErrorsItem] | Unset
    ) = UNSET
    prepare_time: int | None | Unset = UNSET
    private: bool | Unset = UNSET
    received_date: datetime.date | None | Unset = UNSET
    received_from: CreateSubmittalResponse201ReceivedFromType0 | None | Unset = UNSET
    rejected_submittal_log_approver_id: int | None | Unset = UNSET
    required_on_site_date: datetime.date | None | Unset = UNSET
    responsible_contractor: (
        CreateSubmittalResponse201ResponsibleContractorType0 | None | Unset
    ) = UNSET
    revision: str | Unset = UNSET
    rich_text_description: str | Unset = UNSET
    scheduled_task: CreateSubmittalResponse201ScheduledTaskType0 | None | Unset = UNSET
    source_submittal_log_id: int | Unset = UNSET
    specification_section: CreateSubmittalResponse201SpecificationSection | Unset = (
        UNSET
    )
    status: CreateSubmittalResponse201Status | Unset = UNSET
    sub_job: CreateSubmittalResponse201SubJobType0 | None | Unset = UNSET
    submit_by: datetime.date | None | Unset = UNSET
    submittal_manager: CreateSubmittalResponse201SubmittalManager | Unset = UNSET
    submittal_package: CreateSubmittalResponse201SubmittalPackage | Unset = UNSET
    submittal_workflow_template: (
        CreateSubmittalResponse201SubmittalWorkflowTemplateType0 | None | Unset
    ) = UNSET
    submittal_workflow_template_applied_at: datetime.datetime | None | Unset = UNSET
    title: str | Unset = UNSET
    type_: CreateSubmittalResponse201Type | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.create_submittal_response_201_cost_code_type_0 import (
            CreateSubmittalResponse201CostCodeType0,
        )
        from ..models.create_submittal_response_201_location_type_0 import (
            CreateSubmittalResponse201LocationType0,
        )
        from ..models.create_submittal_response_201_received_from_type_0 import (
            CreateSubmittalResponse201ReceivedFromType0,
        )
        from ..models.create_submittal_response_201_responsible_contractor_type_0 import (
            CreateSubmittalResponse201ResponsibleContractorType0,
        )
        from ..models.create_submittal_response_201_scheduled_task_type_0 import (
            CreateSubmittalResponse201ScheduledTaskType0,
        )
        from ..models.create_submittal_response_201_sub_job_type_0 import (
            CreateSubmittalResponse201SubJobType0,
        )
        from ..models.create_submittal_response_201_submittal_workflow_template_type_0 import (
            CreateSubmittalResponse201SubmittalWorkflowTemplateType0,
        )

        actual_delivery_date: None | str | Unset
        if isinstance(self.actual_delivery_date, Unset):
            actual_delivery_date = UNSET
        elif isinstance(self.actual_delivery_date, datetime.date):
            actual_delivery_date = self.actual_delivery_date.isoformat()
        else:
            actual_delivery_date = self.actual_delivery_date

        approvers: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.approvers, Unset):
            approvers = []
            for approvers_item_data in self.approvers:
                approvers_item = approvers_item_data.to_dict()
                approvers.append(approvers_item)

        attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_dict()
                attachments.append(attachments_item)

        attachments_count = self.attachments_count

        ball_in_court: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.ball_in_court, Unset):
            ball_in_court = []
            for ball_in_court_item_data in self.ball_in_court:
                ball_in_court_item = ball_in_court_item_data.to_dict()
                ball_in_court.append(ball_in_court_item)

        buffer_time: int | None | Unset
        if isinstance(self.buffer_time, Unset):
            buffer_time = UNSET
        else:
            buffer_time = self.buffer_time

        closed_at: None | str | Unset
        if isinstance(self.closed_at, Unset):
            closed_at = UNSET
        elif isinstance(self.closed_at, datetime.datetime):
            closed_at = self.closed_at.isoformat()
        else:
            closed_at = self.closed_at

        confirmed_delivery_date: None | str | Unset
        if isinstance(self.confirmed_delivery_date, Unset):
            confirmed_delivery_date = UNSET
        elif isinstance(self.confirmed_delivery_date, datetime.date):
            confirmed_delivery_date = self.confirmed_delivery_date.isoformat()
        else:
            confirmed_delivery_date = self.confirmed_delivery_date

        cost_code: dict[str, Any] | None | Unset
        if isinstance(self.cost_code, Unset):
            cost_code = UNSET
        elif isinstance(self.cost_code, CreateSubmittalResponse201CostCodeType0):
            cost_code = self.cost_code.to_dict()
        else:
            cost_code = self.cost_code

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

        custom_textarea_1: None | str | Unset
        if isinstance(self.custom_textarea_1, Unset):
            custom_textarea_1 = UNSET
        else:
            custom_textarea_1 = self.custom_textarea_1

        custom_textfield_1: None | str | Unset
        if isinstance(self.custom_textfield_1, Unset):
            custom_textfield_1 = UNSET
        else:
            custom_textfield_1 = self.custom_textfield_1

        deleted_at: str | Unset = UNSET
        if not isinstance(self.deleted_at, Unset):
            deleted_at = self.deleted_at.isoformat()

        description = self.description

        design_team_review_time: int | None | Unset
        if isinstance(self.design_team_review_time, Unset):
            design_team_review_time = UNSET
        else:
            design_team_review_time = self.design_team_review_time

        distributed_at: None | str | Unset
        if isinstance(self.distributed_at, Unset):
            distributed_at = UNSET
        elif isinstance(self.distributed_at, datetime.datetime):
            distributed_at = self.distributed_at.isoformat()
        else:
            distributed_at = self.distributed_at

        distributed_submittals: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distributed_submittals, Unset):
            distributed_submittals = []
            for distributed_submittals_item_data in self.distributed_submittals:
                distributed_submittals_item = distributed_submittals_item_data.to_dict()
                distributed_submittals.append(distributed_submittals_item)

        distribution_members: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distribution_members, Unset):
            distribution_members = []
            for distribution_members_item_data in self.distribution_members:
                distribution_members_item = distribution_members_item_data.to_dict()
                distribution_members.append(distribution_members_item)

        due_date: None | str | Unset
        if isinstance(self.due_date, Unset):
            due_date = UNSET
        elif isinstance(self.due_date, datetime.date):
            due_date = self.due_date.isoformat()
        else:
            due_date = self.due_date

        for_record_only = self.for_record_only

        formatted_number = self.formatted_number

        id = self.id

        internal_review_time: int | None | Unset
        if isinstance(self.internal_review_time, Unset):
            internal_review_time = UNSET
        else:
            internal_review_time = self.internal_review_time

        is_rejected = self.is_rejected

        issue_date: None | str | Unset
        if isinstance(self.issue_date, Unset):
            issue_date = UNSET
        elif isinstance(self.issue_date, datetime.date):
            issue_date = self.issue_date.isoformat()
        else:
            issue_date = self.issue_date

        lead_time: int | None | Unset
        if isinstance(self.lead_time, Unset):
            lead_time = UNSET
        else:
            lead_time = self.lead_time

        location: dict[str, Any] | None | Unset
        if isinstance(self.location, Unset):
            location = UNSET
        elif isinstance(self.location, CreateSubmittalResponse201LocationType0):
            location = self.location.to_dict()
        else:
            location = self.location

        number = self.number

        open_date: None | str | Unset
        if isinstance(self.open_date, Unset):
            open_date = UNSET
        elif isinstance(self.open_date, datetime.date):
            open_date = self.open_date.isoformat()
        else:
            open_date = self.open_date

        operation_item_errors: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.operation_item_errors, Unset):
            operation_item_errors = []
            for operation_item_errors_item_data in self.operation_item_errors:
                operation_item_errors_item = operation_item_errors_item_data.to_dict()
                operation_item_errors.append(operation_item_errors_item)

        prepare_time: int | None | Unset
        if isinstance(self.prepare_time, Unset):
            prepare_time = UNSET
        else:
            prepare_time = self.prepare_time

        private = self.private

        received_date: None | str | Unset
        if isinstance(self.received_date, Unset):
            received_date = UNSET
        elif isinstance(self.received_date, datetime.date):
            received_date = self.received_date.isoformat()
        else:
            received_date = self.received_date

        received_from: dict[str, Any] | None | Unset
        if isinstance(self.received_from, Unset):
            received_from = UNSET
        elif isinstance(
            self.received_from, CreateSubmittalResponse201ReceivedFromType0
        ):
            received_from = self.received_from.to_dict()
        else:
            received_from = self.received_from

        rejected_submittal_log_approver_id: int | None | Unset
        if isinstance(self.rejected_submittal_log_approver_id, Unset):
            rejected_submittal_log_approver_id = UNSET
        else:
            rejected_submittal_log_approver_id = self.rejected_submittal_log_approver_id

        required_on_site_date: None | str | Unset
        if isinstance(self.required_on_site_date, Unset):
            required_on_site_date = UNSET
        elif isinstance(self.required_on_site_date, datetime.date):
            required_on_site_date = self.required_on_site_date.isoformat()
        else:
            required_on_site_date = self.required_on_site_date

        responsible_contractor: dict[str, Any] | None | Unset
        if isinstance(self.responsible_contractor, Unset):
            responsible_contractor = UNSET
        elif isinstance(
            self.responsible_contractor,
            CreateSubmittalResponse201ResponsibleContractorType0,
        ):
            responsible_contractor = self.responsible_contractor.to_dict()
        else:
            responsible_contractor = self.responsible_contractor

        revision = self.revision

        rich_text_description = self.rich_text_description

        scheduled_task: dict[str, Any] | None | Unset
        if isinstance(self.scheduled_task, Unset):
            scheduled_task = UNSET
        elif isinstance(
            self.scheduled_task, CreateSubmittalResponse201ScheduledTaskType0
        ):
            scheduled_task = self.scheduled_task.to_dict()
        else:
            scheduled_task = self.scheduled_task

        source_submittal_log_id = self.source_submittal_log_id

        specification_section: dict[str, Any] | Unset = UNSET
        if not isinstance(self.specification_section, Unset):
            specification_section = self.specification_section.to_dict()

        status: dict[str, Any] | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.to_dict()

        sub_job: dict[str, Any] | None | Unset
        if isinstance(self.sub_job, Unset):
            sub_job = UNSET
        elif isinstance(self.sub_job, CreateSubmittalResponse201SubJobType0):
            sub_job = self.sub_job.to_dict()
        else:
            sub_job = self.sub_job

        submit_by: None | str | Unset
        if isinstance(self.submit_by, Unset):
            submit_by = UNSET
        elif isinstance(self.submit_by, datetime.date):
            submit_by = self.submit_by.isoformat()
        else:
            submit_by = self.submit_by

        submittal_manager: dict[str, Any] | Unset = UNSET
        if not isinstance(self.submittal_manager, Unset):
            submittal_manager = self.submittal_manager.to_dict()

        submittal_package: dict[str, Any] | Unset = UNSET
        if not isinstance(self.submittal_package, Unset):
            submittal_package = self.submittal_package.to_dict()

        submittal_workflow_template: dict[str, Any] | None | Unset
        if isinstance(self.submittal_workflow_template, Unset):
            submittal_workflow_template = UNSET
        elif isinstance(
            self.submittal_workflow_template,
            CreateSubmittalResponse201SubmittalWorkflowTemplateType0,
        ):
            submittal_workflow_template = self.submittal_workflow_template.to_dict()
        else:
            submittal_workflow_template = self.submittal_workflow_template

        submittal_workflow_template_applied_at: None | str | Unset
        if isinstance(self.submittal_workflow_template_applied_at, Unset):
            submittal_workflow_template_applied_at = UNSET
        elif isinstance(self.submittal_workflow_template_applied_at, datetime.datetime):
            submittal_workflow_template_applied_at = (
                self.submittal_workflow_template_applied_at.isoformat()
            )
        else:
            submittal_workflow_template_applied_at = (
                self.submittal_workflow_template_applied_at
            )

        title = self.title

        type_: dict[str, Any] | Unset = UNSET
        if not isinstance(self.type_, Unset):
            type_ = self.type_.to_dict()

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if actual_delivery_date is not UNSET:
            field_dict["actual_delivery_date"] = actual_delivery_date
        if approvers is not UNSET:
            field_dict["approvers"] = approvers
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if attachments_count is not UNSET:
            field_dict["attachments_count"] = attachments_count
        if ball_in_court is not UNSET:
            field_dict["ball_in_court"] = ball_in_court
        if buffer_time is not UNSET:
            field_dict["buffer_time"] = buffer_time
        if closed_at is not UNSET:
            field_dict["closed_at"] = closed_at
        if confirmed_delivery_date is not UNSET:
            field_dict["confirmed_delivery_date"] = confirmed_delivery_date
        if cost_code is not UNSET:
            field_dict["cost_code"] = cost_code
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if current_revision is not UNSET:
            field_dict["current_revision"] = current_revision
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if custom_textarea_1 is not UNSET:
            field_dict["custom_textarea_1"] = custom_textarea_1
        if custom_textfield_1 is not UNSET:
            field_dict["custom_textfield_1"] = custom_textfield_1
        if deleted_at is not UNSET:
            field_dict["deleted_at"] = deleted_at
        if description is not UNSET:
            field_dict["description"] = description
        if design_team_review_time is not UNSET:
            field_dict["design_team_review_time"] = design_team_review_time
        if distributed_at is not UNSET:
            field_dict["distributed_at"] = distributed_at
        if distributed_submittals is not UNSET:
            field_dict["distributed_submittals"] = distributed_submittals
        if distribution_members is not UNSET:
            field_dict["distribution_members"] = distribution_members
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if for_record_only is not UNSET:
            field_dict["for_record_only"] = for_record_only
        if formatted_number is not UNSET:
            field_dict["formatted_number"] = formatted_number
        if id is not UNSET:
            field_dict["id"] = id
        if internal_review_time is not UNSET:
            field_dict["internal_review_time"] = internal_review_time
        if is_rejected is not UNSET:
            field_dict["is_rejected"] = is_rejected
        if issue_date is not UNSET:
            field_dict["issue_date"] = issue_date
        if lead_time is not UNSET:
            field_dict["lead_time"] = lead_time
        if location is not UNSET:
            field_dict["location"] = location
        if number is not UNSET:
            field_dict["number"] = number
        if open_date is not UNSET:
            field_dict["open_date"] = open_date
        if operation_item_errors is not UNSET:
            field_dict["operation_item_errors"] = operation_item_errors
        if prepare_time is not UNSET:
            field_dict["prepare_time"] = prepare_time
        if private is not UNSET:
            field_dict["private"] = private
        if received_date is not UNSET:
            field_dict["received_date"] = received_date
        if received_from is not UNSET:
            field_dict["received_from"] = received_from
        if rejected_submittal_log_approver_id is not UNSET:
            field_dict["rejected_submittal_log_approver_id"] = (
                rejected_submittal_log_approver_id
            )
        if required_on_site_date is not UNSET:
            field_dict["required_on_site_date"] = required_on_site_date
        if responsible_contractor is not UNSET:
            field_dict["responsible_contractor"] = responsible_contractor
        if revision is not UNSET:
            field_dict["revision"] = revision
        if rich_text_description is not UNSET:
            field_dict["rich_text_description"] = rich_text_description
        if scheduled_task is not UNSET:
            field_dict["scheduled_task"] = scheduled_task
        if source_submittal_log_id is not UNSET:
            field_dict["source_submittal_log_id"] = source_submittal_log_id
        if specification_section is not UNSET:
            field_dict["specification_section"] = specification_section
        if status is not UNSET:
            field_dict["status"] = status
        if sub_job is not UNSET:
            field_dict["sub_job"] = sub_job
        if submit_by is not UNSET:
            field_dict["submit_by"] = submit_by
        if submittal_manager is not UNSET:
            field_dict["submittal_manager"] = submittal_manager
        if submittal_package is not UNSET:
            field_dict["submittal_package"] = submittal_package
        if submittal_workflow_template is not UNSET:
            field_dict["submittal_workflow_template"] = submittal_workflow_template
        if submittal_workflow_template_applied_at is not UNSET:
            field_dict["submittal_workflow_template_applied_at"] = (
                submittal_workflow_template_applied_at
            )
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_submittal_response_201_approvers_item import (
            CreateSubmittalResponse201ApproversItem,
        )
        from ..models.create_submittal_response_201_attachments_item import (
            CreateSubmittalResponse201AttachmentsItem,
        )
        from ..models.create_submittal_response_201_ball_in_court_item import (
            CreateSubmittalResponse201BallInCourtItem,
        )
        from ..models.create_submittal_response_201_cost_code_type_0 import (
            CreateSubmittalResponse201CostCodeType0,
        )
        from ..models.create_submittal_response_201_created_by import (
            CreateSubmittalResponse201CreatedBy,
        )
        from ..models.create_submittal_response_201_custom_fields import (
            CreateSubmittalResponse201CustomFields,
        )
        from ..models.create_submittal_response_201_distributed_submittals_item import (
            CreateSubmittalResponse201DistributedSubmittalsItem,
        )
        from ..models.create_submittal_response_201_distribution_members_item import (
            CreateSubmittalResponse201DistributionMembersItem,
        )
        from ..models.create_submittal_response_201_location_type_0 import (
            CreateSubmittalResponse201LocationType0,
        )
        from ..models.create_submittal_response_201_operation_item_errors_item import (
            CreateSubmittalResponse201OperationItemErrorsItem,
        )
        from ..models.create_submittal_response_201_received_from_type_0 import (
            CreateSubmittalResponse201ReceivedFromType0,
        )
        from ..models.create_submittal_response_201_responsible_contractor_type_0 import (
            CreateSubmittalResponse201ResponsibleContractorType0,
        )
        from ..models.create_submittal_response_201_scheduled_task_type_0 import (
            CreateSubmittalResponse201ScheduledTaskType0,
        )
        from ..models.create_submittal_response_201_specification_section import (
            CreateSubmittalResponse201SpecificationSection,
        )
        from ..models.create_submittal_response_201_status import (
            CreateSubmittalResponse201Status,
        )
        from ..models.create_submittal_response_201_sub_job_type_0 import (
            CreateSubmittalResponse201SubJobType0,
        )
        from ..models.create_submittal_response_201_submittal_manager import (
            CreateSubmittalResponse201SubmittalManager,
        )
        from ..models.create_submittal_response_201_submittal_package import (
            CreateSubmittalResponse201SubmittalPackage,
        )
        from ..models.create_submittal_response_201_submittal_workflow_template_type_0 import (
            CreateSubmittalResponse201SubmittalWorkflowTemplateType0,
        )
        from ..models.create_submittal_response_201_type import (
            CreateSubmittalResponse201Type,
        )

        d = dict(src_dict)

        def _parse_actual_delivery_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                actual_delivery_date_type_0 = datetime.date.fromisoformat(data)

                return actual_delivery_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        actual_delivery_date = _parse_actual_delivery_date(
            d.pop("actual_delivery_date", UNSET)
        )

        _approvers = d.pop("approvers", UNSET)
        approvers: list[CreateSubmittalResponse201ApproversItem] | Unset = UNSET
        if _approvers is not UNSET:
            approvers = []
            for approvers_item_data in _approvers:
                approvers_item = CreateSubmittalResponse201ApproversItem.from_dict(
                    approvers_item_data
                )

                approvers.append(approvers_item)

        _attachments = d.pop("attachments", UNSET)
        attachments: list[CreateSubmittalResponse201AttachmentsItem] | Unset = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = CreateSubmittalResponse201AttachmentsItem.from_dict(
                    attachments_item_data
                )

                attachments.append(attachments_item)

        attachments_count = d.pop("attachments_count", UNSET)

        _ball_in_court = d.pop("ball_in_court", UNSET)
        ball_in_court: list[CreateSubmittalResponse201BallInCourtItem] | Unset = UNSET
        if _ball_in_court is not UNSET:
            ball_in_court = []
            for ball_in_court_item_data in _ball_in_court:
                ball_in_court_item = (
                    CreateSubmittalResponse201BallInCourtItem.from_dict(
                        ball_in_court_item_data
                    )
                )

                ball_in_court.append(ball_in_court_item)

        def _parse_buffer_time(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        buffer_time = _parse_buffer_time(d.pop("buffer_time", UNSET))

        def _parse_closed_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                closed_at_type_0 = datetime.datetime.fromisoformat(data)

                return closed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        closed_at = _parse_closed_at(d.pop("closed_at", UNSET))

        def _parse_confirmed_delivery_date(
            data: object,
        ) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                confirmed_delivery_date_type_0 = datetime.date.fromisoformat(data)

                return confirmed_delivery_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        confirmed_delivery_date = _parse_confirmed_delivery_date(
            d.pop("confirmed_delivery_date", UNSET)
        )

        def _parse_cost_code(
            data: object,
        ) -> CreateSubmittalResponse201CostCodeType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                cost_code_type_0 = CreateSubmittalResponse201CostCodeType0.from_dict(
                    data
                )

                return cost_code_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateSubmittalResponse201CostCodeType0 | None | Unset, data)

        cost_code = _parse_cost_code(d.pop("cost_code", UNSET))

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _created_by = d.pop("created_by", UNSET)
        created_by: CreateSubmittalResponse201CreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = CreateSubmittalResponse201CreatedBy.from_dict(_created_by)

        current_revision = d.pop("current_revision", UNSET)

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: CreateSubmittalResponse201CustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = CreateSubmittalResponse201CustomFields.from_dict(
                _custom_fields
            )

        def _parse_custom_textarea_1(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        custom_textarea_1 = _parse_custom_textarea_1(d.pop("custom_textarea_1", UNSET))

        def _parse_custom_textfield_1(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        custom_textfield_1 = _parse_custom_textfield_1(
            d.pop("custom_textfield_1", UNSET)
        )

        _deleted_at = d.pop("deleted_at", UNSET)
        deleted_at: datetime.datetime | Unset
        if isinstance(_deleted_at, Unset):
            deleted_at = UNSET
        else:
            deleted_at = datetime.datetime.fromisoformat(_deleted_at)

        description = d.pop("description", UNSET)

        def _parse_design_team_review_time(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        design_team_review_time = _parse_design_team_review_time(
            d.pop("design_team_review_time", UNSET)
        )

        def _parse_distributed_at(data: object) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                distributed_at_type_0 = datetime.datetime.fromisoformat(data)

                return distributed_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        distributed_at = _parse_distributed_at(d.pop("distributed_at", UNSET))

        _distributed_submittals = d.pop("distributed_submittals", UNSET)
        distributed_submittals: (
            list[CreateSubmittalResponse201DistributedSubmittalsItem] | Unset
        ) = UNSET
        if _distributed_submittals is not UNSET:
            distributed_submittals = []
            for distributed_submittals_item_data in _distributed_submittals:
                distributed_submittals_item = (
                    CreateSubmittalResponse201DistributedSubmittalsItem.from_dict(
                        distributed_submittals_item_data
                    )
                )

                distributed_submittals.append(distributed_submittals_item)

        _distribution_members = d.pop("distribution_members", UNSET)
        distribution_members: (
            list[CreateSubmittalResponse201DistributionMembersItem] | Unset
        ) = UNSET
        if _distribution_members is not UNSET:
            distribution_members = []
            for distribution_members_item_data in _distribution_members:
                distribution_members_item = (
                    CreateSubmittalResponse201DistributionMembersItem.from_dict(
                        distribution_members_item_data
                    )
                )

                distribution_members.append(distribution_members_item)

        def _parse_due_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                due_date_type_0 = datetime.date.fromisoformat(data)

                return due_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        due_date = _parse_due_date(d.pop("due_date", UNSET))

        for_record_only = d.pop("for_record_only", UNSET)

        formatted_number = d.pop("formatted_number", UNSET)

        id = d.pop("id", UNSET)

        def _parse_internal_review_time(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        internal_review_time = _parse_internal_review_time(
            d.pop("internal_review_time", UNSET)
        )

        is_rejected = d.pop("is_rejected", UNSET)

        def _parse_issue_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                issue_date_type_0 = datetime.date.fromisoformat(data)

                return issue_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        issue_date = _parse_issue_date(d.pop("issue_date", UNSET))

        def _parse_lead_time(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        lead_time = _parse_lead_time(d.pop("lead_time", UNSET))

        def _parse_location(
            data: object,
        ) -> CreateSubmittalResponse201LocationType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                location_type_0 = CreateSubmittalResponse201LocationType0.from_dict(
                    data
                )

                return location_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateSubmittalResponse201LocationType0 | None | Unset, data)

        location = _parse_location(d.pop("location", UNSET))

        number = d.pop("number", UNSET)

        def _parse_open_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                open_date_type_0 = datetime.date.fromisoformat(data)

                return open_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        open_date = _parse_open_date(d.pop("open_date", UNSET))

        _operation_item_errors = d.pop("operation_item_errors", UNSET)
        operation_item_errors: (
            list[CreateSubmittalResponse201OperationItemErrorsItem] | Unset
        ) = UNSET
        if _operation_item_errors is not UNSET:
            operation_item_errors = []
            for operation_item_errors_item_data in _operation_item_errors:
                operation_item_errors_item = (
                    CreateSubmittalResponse201OperationItemErrorsItem.from_dict(
                        operation_item_errors_item_data
                    )
                )

                operation_item_errors.append(operation_item_errors_item)

        def _parse_prepare_time(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        prepare_time = _parse_prepare_time(d.pop("prepare_time", UNSET))

        private = d.pop("private", UNSET)

        def _parse_received_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                received_date_type_0 = datetime.date.fromisoformat(data)

                return received_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        received_date = _parse_received_date(d.pop("received_date", UNSET))

        def _parse_received_from(
            data: object,
        ) -> CreateSubmittalResponse201ReceivedFromType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                received_from_type_0 = (
                    CreateSubmittalResponse201ReceivedFromType0.from_dict(data)
                )

                return received_from_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateSubmittalResponse201ReceivedFromType0 | None | Unset, data
            )

        received_from = _parse_received_from(d.pop("received_from", UNSET))

        def _parse_rejected_submittal_log_approver_id(
            data: object,
        ) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        rejected_submittal_log_approver_id = _parse_rejected_submittal_log_approver_id(
            d.pop("rejected_submittal_log_approver_id", UNSET)
        )

        def _parse_required_on_site_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                required_on_site_date_type_0 = datetime.date.fromisoformat(data)

                return required_on_site_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        required_on_site_date = _parse_required_on_site_date(
            d.pop("required_on_site_date", UNSET)
        )

        def _parse_responsible_contractor(
            data: object,
        ) -> CreateSubmittalResponse201ResponsibleContractorType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                responsible_contractor_type_0 = (
                    CreateSubmittalResponse201ResponsibleContractorType0.from_dict(data)
                )

                return responsible_contractor_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateSubmittalResponse201ResponsibleContractorType0 | None | Unset,
                data,
            )

        responsible_contractor = _parse_responsible_contractor(
            d.pop("responsible_contractor", UNSET)
        )

        revision = d.pop("revision", UNSET)

        rich_text_description = d.pop("rich_text_description", UNSET)

        def _parse_scheduled_task(
            data: object,
        ) -> CreateSubmittalResponse201ScheduledTaskType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                scheduled_task_type_0 = (
                    CreateSubmittalResponse201ScheduledTaskType0.from_dict(data)
                )

                return scheduled_task_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateSubmittalResponse201ScheduledTaskType0 | None | Unset, data
            )

        scheduled_task = _parse_scheduled_task(d.pop("scheduled_task", UNSET))

        source_submittal_log_id = d.pop("source_submittal_log_id", UNSET)

        _specification_section = d.pop("specification_section", UNSET)
        specification_section: CreateSubmittalResponse201SpecificationSection | Unset
        if isinstance(_specification_section, Unset):
            specification_section = UNSET
        else:
            specification_section = (
                CreateSubmittalResponse201SpecificationSection.from_dict(
                    _specification_section
                )
            )

        _status = d.pop("status", UNSET)
        status: CreateSubmittalResponse201Status | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = CreateSubmittalResponse201Status.from_dict(_status)

        def _parse_sub_job(
            data: object,
        ) -> CreateSubmittalResponse201SubJobType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                sub_job_type_0 = CreateSubmittalResponse201SubJobType0.from_dict(data)

                return sub_job_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(CreateSubmittalResponse201SubJobType0 | None | Unset, data)

        sub_job = _parse_sub_job(d.pop("sub_job", UNSET))

        def _parse_submit_by(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                submit_by_type_0 = datetime.date.fromisoformat(data)

                return submit_by_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        submit_by = _parse_submit_by(d.pop("submit_by", UNSET))

        _submittal_manager = d.pop("submittal_manager", UNSET)
        submittal_manager: CreateSubmittalResponse201SubmittalManager | Unset
        if isinstance(_submittal_manager, Unset):
            submittal_manager = UNSET
        else:
            submittal_manager = CreateSubmittalResponse201SubmittalManager.from_dict(
                _submittal_manager
            )

        _submittal_package = d.pop("submittal_package", UNSET)
        submittal_package: CreateSubmittalResponse201SubmittalPackage | Unset
        if isinstance(_submittal_package, Unset):
            submittal_package = UNSET
        else:
            submittal_package = CreateSubmittalResponse201SubmittalPackage.from_dict(
                _submittal_package
            )

        def _parse_submittal_workflow_template(
            data: object,
        ) -> CreateSubmittalResponse201SubmittalWorkflowTemplateType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                submittal_workflow_template_type_0 = (
                    CreateSubmittalResponse201SubmittalWorkflowTemplateType0.from_dict(
                        data
                    )
                )

                return submittal_workflow_template_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                CreateSubmittalResponse201SubmittalWorkflowTemplateType0 | None | Unset,
                data,
            )

        submittal_workflow_template = _parse_submittal_workflow_template(
            d.pop("submittal_workflow_template", UNSET)
        )

        def _parse_submittal_workflow_template_applied_at(
            data: object,
        ) -> datetime.datetime | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                submittal_workflow_template_applied_at_type_0 = (
                    datetime.datetime.fromisoformat(data)
                )

                return submittal_workflow_template_applied_at_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.datetime | None | Unset, data)

        submittal_workflow_template_applied_at = (
            _parse_submittal_workflow_template_applied_at(
                d.pop("submittal_workflow_template_applied_at", UNSET)
            )
        )

        title = d.pop("title", UNSET)

        _type_ = d.pop("type", UNSET)
        type_: CreateSubmittalResponse201Type | Unset
        if isinstance(_type_, Unset):
            type_ = UNSET
        else:
            type_ = CreateSubmittalResponse201Type.from_dict(_type_)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        create_submittal_response_201 = cls(
            actual_delivery_date=actual_delivery_date,
            approvers=approvers,
            attachments=attachments,
            attachments_count=attachments_count,
            ball_in_court=ball_in_court,
            buffer_time=buffer_time,
            closed_at=closed_at,
            confirmed_delivery_date=confirmed_delivery_date,
            cost_code=cost_code,
            created_at=created_at,
            created_by=created_by,
            current_revision=current_revision,
            custom_fields=custom_fields,
            custom_textarea_1=custom_textarea_1,
            custom_textfield_1=custom_textfield_1,
            deleted_at=deleted_at,
            description=description,
            design_team_review_time=design_team_review_time,
            distributed_at=distributed_at,
            distributed_submittals=distributed_submittals,
            distribution_members=distribution_members,
            due_date=due_date,
            for_record_only=for_record_only,
            formatted_number=formatted_number,
            id=id,
            internal_review_time=internal_review_time,
            is_rejected=is_rejected,
            issue_date=issue_date,
            lead_time=lead_time,
            location=location,
            number=number,
            open_date=open_date,
            operation_item_errors=operation_item_errors,
            prepare_time=prepare_time,
            private=private,
            received_date=received_date,
            received_from=received_from,
            rejected_submittal_log_approver_id=rejected_submittal_log_approver_id,
            required_on_site_date=required_on_site_date,
            responsible_contractor=responsible_contractor,
            revision=revision,
            rich_text_description=rich_text_description,
            scheduled_task=scheduled_task,
            source_submittal_log_id=source_submittal_log_id,
            specification_section=specification_section,
            status=status,
            sub_job=sub_job,
            submit_by=submit_by,
            submittal_manager=submittal_manager,
            submittal_package=submittal_package,
            submittal_workflow_template=submittal_workflow_template,
            submittal_workflow_template_applied_at=submittal_workflow_template_applied_at,
            title=title,
            type_=type_,
            updated_at=updated_at,
        )

        create_submittal_response_201.additional_properties = d
        return create_submittal_response_201

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
