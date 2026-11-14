from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_submittals_response_200_item_approvers_item import (
        ListSubmittalsResponse200ItemApproversItem,
    )
    from ..models.list_submittals_response_200_item_associated_attachments_item import (
        ListSubmittalsResponse200ItemAssociatedAttachmentsItem,
    )
    from ..models.list_submittals_response_200_item_ball_in_court_item import (
        ListSubmittalsResponse200ItemBallInCourtItem,
    )
    from ..models.list_submittals_response_200_item_created_by import (
        ListSubmittalsResponse200ItemCreatedBy,
    )
    from ..models.list_submittals_response_200_item_custom_fields import (
        ListSubmittalsResponse200ItemCustomFields,
    )
    from ..models.list_submittals_response_200_item_distribution_members_item import (
        ListSubmittalsResponse200ItemDistributionMembersItem,
    )
    from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0 import (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0,
    )
    from ..models.list_submittals_response_200_item_received_from_type_0 import (
        ListSubmittalsResponse200ItemReceivedFromType0,
    )
    from ..models.list_submittals_response_200_item_responsible_contractor_type_0 import (
        ListSubmittalsResponse200ItemResponsibleContractorType0,
    )
    from ..models.list_submittals_response_200_item_scheduled_task import (
        ListSubmittalsResponse200ItemScheduledTask,
    )
    from ..models.list_submittals_response_200_item_specification_section_type_0 import (
        ListSubmittalsResponse200ItemSpecificationSectionType0,
    )
    from ..models.list_submittals_response_200_item_status import (
        ListSubmittalsResponse200ItemStatus,
    )
    from ..models.list_submittals_response_200_item_submittal_manager_type_0 import (
        ListSubmittalsResponse200ItemSubmittalManagerType0,
    )
    from ..models.list_submittals_response_200_item_submittal_package_type_0 import (
        ListSubmittalsResponse200ItemSubmittalPackageType0,
    )
    from ..models.list_submittals_response_200_item_submittal_workflow_template_type_0 import (
        ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0,
    )
    from ..models.list_submittals_response_200_item_type_type_0 import (
        ListSubmittalsResponse200ItemTypeType0,
    )


T = TypeVar("T", bound="ListSubmittalsResponse200Item")


@_attrs_define
class ListSubmittalsResponse200Item:
    """Includes standard submittal fields, workflow details, approvers, and attachments.

    Attributes:
        actual_delivery_date (datetime.date | None | Unset):
        approvers (list[ListSubmittalsResponse200ItemApproversItem] | Unset):
        associated_attachments (list[ListSubmittalsResponse200ItemAssociatedAttachmentsItem] | Unset):
        ball_in_court (list[ListSubmittalsResponse200ItemBallInCourtItem] | Unset):
        closed_at (datetime.datetime | None | Unset): Timestamp when the submittal was closed.
        cost_code_id (int | None | Unset):
        created_at (datetime.datetime | Unset):
        created_by (ListSubmittalsResponse200ItemCreatedBy | Unset):
        current_revision (bool | Unset):
        custom_fields (ListSubmittalsResponse200ItemCustomFields | Unset):
        description (str | Unset):
        distributed_at (datetime.datetime | Unset):
        distribution_members (list[ListSubmittalsResponse200ItemDistributionMembersItem] | Unset):
        drawing_ids (list[int] | Unset):
        due_date (datetime.date | Unset):
        formatted_number (str | Unset):
        id (int | Unset):
        issue_date (datetime.date | Unset):
        last_distributed_submittal (ListSubmittalsResponse200ItemLastDistributedSubmittalType0 | None | Unset):
        lead_time (int | Unset):
        linked_drawing_ids (list[int] | Unset):
        location_id (int | None | Unset):
        number (str | Unset):
        private (bool | Unset):
        received_date (datetime.date | Unset):
        received_from (ListSubmittalsResponse200ItemReceivedFromType0 | None | Unset):
        required_on_site_date (datetime.date | Unset):
        responsible_contractor (ListSubmittalsResponse200ItemResponsibleContractorType0 | None | Unset):
        revision (str | Unset):
        scheduled_task (ListSubmittalsResponse200ItemScheduledTask | Unset): Information about the scheduled task
            associated with this submittal
        specification_section (ListSubmittalsResponse200ItemSpecificationSectionType0 | None | Unset):
        status (ListSubmittalsResponse200ItemStatus | Unset):
        sub_job_id (int | None | Unset):
        submit_by (datetime.date | Unset):
        submittal_manager (ListSubmittalsResponse200ItemSubmittalManagerType0 | None | Unset):
        submittal_package (ListSubmittalsResponse200ItemSubmittalPackageType0 | None | Unset):
        submittal_workflow_template (ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0 | None | Unset):
        submittal_workflow_template_applied_at (datetime.datetime | None | Unset):
        title (str | Unset):
        type_ (ListSubmittalsResponse200ItemTypeType0 | None | Unset):
        updated_at (datetime.datetime | Unset):
    """

    actual_delivery_date: datetime.date | None | Unset = UNSET
    approvers: list[ListSubmittalsResponse200ItemApproversItem] | Unset = UNSET
    associated_attachments: (
        list[ListSubmittalsResponse200ItemAssociatedAttachmentsItem] | Unset
    ) = UNSET
    ball_in_court: list[ListSubmittalsResponse200ItemBallInCourtItem] | Unset = UNSET
    closed_at: datetime.datetime | None | Unset = UNSET
    cost_code_id: int | None | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: ListSubmittalsResponse200ItemCreatedBy | Unset = UNSET
    current_revision: bool | Unset = UNSET
    custom_fields: ListSubmittalsResponse200ItemCustomFields | Unset = UNSET
    description: str | Unset = UNSET
    distributed_at: datetime.datetime | Unset = UNSET
    distribution_members: (
        list[ListSubmittalsResponse200ItemDistributionMembersItem] | Unset
    ) = UNSET
    drawing_ids: list[int] | Unset = UNSET
    due_date: datetime.date | Unset = UNSET
    formatted_number: str | Unset = UNSET
    id: int | Unset = UNSET
    issue_date: datetime.date | Unset = UNSET
    last_distributed_submittal: (
        ListSubmittalsResponse200ItemLastDistributedSubmittalType0 | None | Unset
    ) = UNSET
    lead_time: int | Unset = UNSET
    linked_drawing_ids: list[int] | Unset = UNSET
    location_id: int | None | Unset = UNSET
    number: str | Unset = UNSET
    private: bool | Unset = UNSET
    received_date: datetime.date | Unset = UNSET
    received_from: ListSubmittalsResponse200ItemReceivedFromType0 | None | Unset = UNSET
    required_on_site_date: datetime.date | Unset = UNSET
    responsible_contractor: (
        ListSubmittalsResponse200ItemResponsibleContractorType0 | None | Unset
    ) = UNSET
    revision: str | Unset = UNSET
    scheduled_task: ListSubmittalsResponse200ItemScheduledTask | Unset = UNSET
    specification_section: (
        ListSubmittalsResponse200ItemSpecificationSectionType0 | None | Unset
    ) = UNSET
    status: ListSubmittalsResponse200ItemStatus | Unset = UNSET
    sub_job_id: int | None | Unset = UNSET
    submit_by: datetime.date | Unset = UNSET
    submittal_manager: (
        ListSubmittalsResponse200ItemSubmittalManagerType0 | None | Unset
    ) = UNSET
    submittal_package: (
        ListSubmittalsResponse200ItemSubmittalPackageType0 | None | Unset
    ) = UNSET
    submittal_workflow_template: (
        ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0 | None | Unset
    ) = UNSET
    submittal_workflow_template_applied_at: datetime.datetime | None | Unset = UNSET
    title: str | Unset = UNSET
    type_: ListSubmittalsResponse200ItemTypeType0 | None | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0 import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0,
        )
        from ..models.list_submittals_response_200_item_received_from_type_0 import (
            ListSubmittalsResponse200ItemReceivedFromType0,
        )
        from ..models.list_submittals_response_200_item_responsible_contractor_type_0 import (
            ListSubmittalsResponse200ItemResponsibleContractorType0,
        )
        from ..models.list_submittals_response_200_item_specification_section_type_0 import (
            ListSubmittalsResponse200ItemSpecificationSectionType0,
        )
        from ..models.list_submittals_response_200_item_submittal_manager_type_0 import (
            ListSubmittalsResponse200ItemSubmittalManagerType0,
        )
        from ..models.list_submittals_response_200_item_submittal_package_type_0 import (
            ListSubmittalsResponse200ItemSubmittalPackageType0,
        )
        from ..models.list_submittals_response_200_item_submittal_workflow_template_type_0 import (
            ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0,
        )
        from ..models.list_submittals_response_200_item_type_type_0 import (
            ListSubmittalsResponse200ItemTypeType0,
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

        associated_attachments: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.associated_attachments, Unset):
            associated_attachments = []
            for associated_attachments_item_data in self.associated_attachments:
                associated_attachments_item = associated_attachments_item_data.to_dict()
                associated_attachments.append(associated_attachments_item)

        ball_in_court: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.ball_in_court, Unset):
            ball_in_court = []
            for ball_in_court_item_data in self.ball_in_court:
                ball_in_court_item = ball_in_court_item_data.to_dict()
                ball_in_court.append(ball_in_court_item)

        closed_at: None | str | Unset
        if isinstance(self.closed_at, Unset):
            closed_at = UNSET
        elif isinstance(self.closed_at, datetime.datetime):
            closed_at = self.closed_at.isoformat()
        else:
            closed_at = self.closed_at

        cost_code_id: int | None | Unset
        if isinstance(self.cost_code_id, Unset):
            cost_code_id = UNSET
        else:
            cost_code_id = self.cost_code_id

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

        description = self.description

        distributed_at: str | Unset = UNSET
        if not isinstance(self.distributed_at, Unset):
            distributed_at = self.distributed_at.isoformat()

        distribution_members: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.distribution_members, Unset):
            distribution_members = []
            for distribution_members_item_data in self.distribution_members:
                distribution_members_item = distribution_members_item_data.to_dict()
                distribution_members.append(distribution_members_item)

        drawing_ids: list[int] | Unset = UNSET
        if not isinstance(self.drawing_ids, Unset):
            drawing_ids = self.drawing_ids

        due_date: str | Unset = UNSET
        if not isinstance(self.due_date, Unset):
            due_date = self.due_date.isoformat()

        formatted_number = self.formatted_number

        id = self.id

        issue_date: str | Unset = UNSET
        if not isinstance(self.issue_date, Unset):
            issue_date = self.issue_date.isoformat()

        last_distributed_submittal: dict[str, Any] | None | Unset
        if isinstance(self.last_distributed_submittal, Unset):
            last_distributed_submittal = UNSET
        elif isinstance(
            self.last_distributed_submittal,
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0,
        ):
            last_distributed_submittal = self.last_distributed_submittal.to_dict()
        else:
            last_distributed_submittal = self.last_distributed_submittal

        lead_time = self.lead_time

        linked_drawing_ids: list[int] | Unset = UNSET
        if not isinstance(self.linked_drawing_ids, Unset):
            linked_drawing_ids = self.linked_drawing_ids

        location_id: int | None | Unset
        if isinstance(self.location_id, Unset):
            location_id = UNSET
        else:
            location_id = self.location_id

        number = self.number

        private = self.private

        received_date: str | Unset = UNSET
        if not isinstance(self.received_date, Unset):
            received_date = self.received_date.isoformat()

        received_from: dict[str, Any] | None | Unset
        if isinstance(self.received_from, Unset):
            received_from = UNSET
        elif isinstance(
            self.received_from, ListSubmittalsResponse200ItemReceivedFromType0
        ):
            received_from = self.received_from.to_dict()
        else:
            received_from = self.received_from

        required_on_site_date: str | Unset = UNSET
        if not isinstance(self.required_on_site_date, Unset):
            required_on_site_date = self.required_on_site_date.isoformat()

        responsible_contractor: dict[str, Any] | None | Unset
        if isinstance(self.responsible_contractor, Unset):
            responsible_contractor = UNSET
        elif isinstance(
            self.responsible_contractor,
            ListSubmittalsResponse200ItemResponsibleContractorType0,
        ):
            responsible_contractor = self.responsible_contractor.to_dict()
        else:
            responsible_contractor = self.responsible_contractor

        revision = self.revision

        scheduled_task: dict[str, Any] | Unset = UNSET
        if not isinstance(self.scheduled_task, Unset):
            scheduled_task = self.scheduled_task.to_dict()

        specification_section: dict[str, Any] | None | Unset
        if isinstance(self.specification_section, Unset):
            specification_section = UNSET
        elif isinstance(
            self.specification_section,
            ListSubmittalsResponse200ItemSpecificationSectionType0,
        ):
            specification_section = self.specification_section.to_dict()
        else:
            specification_section = self.specification_section

        status: dict[str, Any] | Unset = UNSET
        if not isinstance(self.status, Unset):
            status = self.status.to_dict()

        sub_job_id: int | None | Unset
        if isinstance(self.sub_job_id, Unset):
            sub_job_id = UNSET
        else:
            sub_job_id = self.sub_job_id

        submit_by: str | Unset = UNSET
        if not isinstance(self.submit_by, Unset):
            submit_by = self.submit_by.isoformat()

        submittal_manager: dict[str, Any] | None | Unset
        if isinstance(self.submittal_manager, Unset):
            submittal_manager = UNSET
        elif isinstance(
            self.submittal_manager, ListSubmittalsResponse200ItemSubmittalManagerType0
        ):
            submittal_manager = self.submittal_manager.to_dict()
        else:
            submittal_manager = self.submittal_manager

        submittal_package: dict[str, Any] | None | Unset
        if isinstance(self.submittal_package, Unset):
            submittal_package = UNSET
        elif isinstance(
            self.submittal_package, ListSubmittalsResponse200ItemSubmittalPackageType0
        ):
            submittal_package = self.submittal_package.to_dict()
        else:
            submittal_package = self.submittal_package

        submittal_workflow_template: dict[str, Any] | None | Unset
        if isinstance(self.submittal_workflow_template, Unset):
            submittal_workflow_template = UNSET
        elif isinstance(
            self.submittal_workflow_template,
            ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0,
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

        type_: dict[str, Any] | None | Unset
        if isinstance(self.type_, Unset):
            type_ = UNSET
        elif isinstance(self.type_, ListSubmittalsResponse200ItemTypeType0):
            type_ = self.type_.to_dict()
        else:
            type_ = self.type_

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
        if associated_attachments is not UNSET:
            field_dict["associated_attachments"] = associated_attachments
        if ball_in_court is not UNSET:
            field_dict["ball_in_court"] = ball_in_court
        if closed_at is not UNSET:
            field_dict["closed_at"] = closed_at
        if cost_code_id is not UNSET:
            field_dict["cost_code_id"] = cost_code_id
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if current_revision is not UNSET:
            field_dict["current_revision"] = current_revision
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if description is not UNSET:
            field_dict["description"] = description
        if distributed_at is not UNSET:
            field_dict["distributed_at"] = distributed_at
        if distribution_members is not UNSET:
            field_dict["distribution_members"] = distribution_members
        if drawing_ids is not UNSET:
            field_dict["drawing_ids"] = drawing_ids
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if formatted_number is not UNSET:
            field_dict["formatted_number"] = formatted_number
        if id is not UNSET:
            field_dict["id"] = id
        if issue_date is not UNSET:
            field_dict["issue_date"] = issue_date
        if last_distributed_submittal is not UNSET:
            field_dict["last_distributed_submittal"] = last_distributed_submittal
        if lead_time is not UNSET:
            field_dict["lead_time"] = lead_time
        if linked_drawing_ids is not UNSET:
            field_dict["linked_drawing_ids"] = linked_drawing_ids
        if location_id is not UNSET:
            field_dict["location_id"] = location_id
        if number is not UNSET:
            field_dict["number"] = number
        if private is not UNSET:
            field_dict["private"] = private
        if received_date is not UNSET:
            field_dict["received_date"] = received_date
        if received_from is not UNSET:
            field_dict["received_from"] = received_from
        if required_on_site_date is not UNSET:
            field_dict["required_on_site_date"] = required_on_site_date
        if responsible_contractor is not UNSET:
            field_dict["responsible_contractor"] = responsible_contractor
        if revision is not UNSET:
            field_dict["revision"] = revision
        if scheduled_task is not UNSET:
            field_dict["scheduled_task"] = scheduled_task
        if specification_section is not UNSET:
            field_dict["specification_section"] = specification_section
        if status is not UNSET:
            field_dict["status"] = status
        if sub_job_id is not UNSET:
            field_dict["sub_job_id"] = sub_job_id
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
        from ..models.list_submittals_response_200_item_approvers_item import (
            ListSubmittalsResponse200ItemApproversItem,
        )
        from ..models.list_submittals_response_200_item_associated_attachments_item import (
            ListSubmittalsResponse200ItemAssociatedAttachmentsItem,
        )
        from ..models.list_submittals_response_200_item_ball_in_court_item import (
            ListSubmittalsResponse200ItemBallInCourtItem,
        )
        from ..models.list_submittals_response_200_item_created_by import (
            ListSubmittalsResponse200ItemCreatedBy,
        )
        from ..models.list_submittals_response_200_item_custom_fields import (
            ListSubmittalsResponse200ItemCustomFields,
        )
        from ..models.list_submittals_response_200_item_distribution_members_item import (
            ListSubmittalsResponse200ItemDistributionMembersItem,
        )
        from ..models.list_submittals_response_200_item_last_distributed_submittal_type_0 import (
            ListSubmittalsResponse200ItemLastDistributedSubmittalType0,
        )
        from ..models.list_submittals_response_200_item_received_from_type_0 import (
            ListSubmittalsResponse200ItemReceivedFromType0,
        )
        from ..models.list_submittals_response_200_item_responsible_contractor_type_0 import (
            ListSubmittalsResponse200ItemResponsibleContractorType0,
        )
        from ..models.list_submittals_response_200_item_scheduled_task import (
            ListSubmittalsResponse200ItemScheduledTask,
        )
        from ..models.list_submittals_response_200_item_specification_section_type_0 import (
            ListSubmittalsResponse200ItemSpecificationSectionType0,
        )
        from ..models.list_submittals_response_200_item_status import (
            ListSubmittalsResponse200ItemStatus,
        )
        from ..models.list_submittals_response_200_item_submittal_manager_type_0 import (
            ListSubmittalsResponse200ItemSubmittalManagerType0,
        )
        from ..models.list_submittals_response_200_item_submittal_package_type_0 import (
            ListSubmittalsResponse200ItemSubmittalPackageType0,
        )
        from ..models.list_submittals_response_200_item_submittal_workflow_template_type_0 import (
            ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0,
        )
        from ..models.list_submittals_response_200_item_type_type_0 import (
            ListSubmittalsResponse200ItemTypeType0,
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
        approvers: list[ListSubmittalsResponse200ItemApproversItem] | Unset = UNSET
        if _approvers is not UNSET:
            approvers = []
            for approvers_item_data in _approvers:
                approvers_item = ListSubmittalsResponse200ItemApproversItem.from_dict(
                    approvers_item_data
                )

                approvers.append(approvers_item)

        _associated_attachments = d.pop("associated_attachments", UNSET)
        associated_attachments: (
            list[ListSubmittalsResponse200ItemAssociatedAttachmentsItem] | Unset
        ) = UNSET
        if _associated_attachments is not UNSET:
            associated_attachments = []
            for associated_attachments_item_data in _associated_attachments:
                associated_attachments_item = (
                    ListSubmittalsResponse200ItemAssociatedAttachmentsItem.from_dict(
                        associated_attachments_item_data
                    )
                )

                associated_attachments.append(associated_attachments_item)

        _ball_in_court = d.pop("ball_in_court", UNSET)
        ball_in_court: list[ListSubmittalsResponse200ItemBallInCourtItem] | Unset = (
            UNSET
        )
        if _ball_in_court is not UNSET:
            ball_in_court = []
            for ball_in_court_item_data in _ball_in_court:
                ball_in_court_item = (
                    ListSubmittalsResponse200ItemBallInCourtItem.from_dict(
                        ball_in_court_item_data
                    )
                )

                ball_in_court.append(ball_in_court_item)

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

        def _parse_cost_code_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        cost_code_id = _parse_cost_code_id(d.pop("cost_code_id", UNSET))

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _created_by = d.pop("created_by", UNSET)
        created_by: ListSubmittalsResponse200ItemCreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = ListSubmittalsResponse200ItemCreatedBy.from_dict(_created_by)

        current_revision = d.pop("current_revision", UNSET)

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: ListSubmittalsResponse200ItemCustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = ListSubmittalsResponse200ItemCustomFields.from_dict(
                _custom_fields
            )

        description = d.pop("description", UNSET)

        _distributed_at = d.pop("distributed_at", UNSET)
        distributed_at: datetime.datetime | Unset
        if isinstance(_distributed_at, Unset):
            distributed_at = UNSET
        else:
            distributed_at = datetime.datetime.fromisoformat(_distributed_at)

        _distribution_members = d.pop("distribution_members", UNSET)
        distribution_members: (
            list[ListSubmittalsResponse200ItemDistributionMembersItem] | Unset
        ) = UNSET
        if _distribution_members is not UNSET:
            distribution_members = []
            for distribution_members_item_data in _distribution_members:
                distribution_members_item = (
                    ListSubmittalsResponse200ItemDistributionMembersItem.from_dict(
                        distribution_members_item_data
                    )
                )

                distribution_members.append(distribution_members_item)

        drawing_ids = cast(list[int], d.pop("drawing_ids", UNSET))

        _due_date = d.pop("due_date", UNSET)
        due_date: datetime.date | Unset
        if isinstance(_due_date, Unset):
            due_date = UNSET
        else:
            due_date = datetime.date.fromisoformat(_due_date)

        formatted_number = d.pop("formatted_number", UNSET)

        id = d.pop("id", UNSET)

        _issue_date = d.pop("issue_date", UNSET)
        issue_date: datetime.date | Unset
        if isinstance(_issue_date, Unset):
            issue_date = UNSET
        else:
            issue_date = datetime.date.fromisoformat(_issue_date)

        def _parse_last_distributed_submittal(
            data: object,
        ) -> ListSubmittalsResponse200ItemLastDistributedSubmittalType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                last_distributed_submittal_type_0 = ListSubmittalsResponse200ItemLastDistributedSubmittalType0.from_dict(
                    data
                )

                return last_distributed_submittal_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemLastDistributedSubmittalType0
                | None
                | Unset,
                data,
            )

        last_distributed_submittal = _parse_last_distributed_submittal(
            d.pop("last_distributed_submittal", UNSET)
        )

        lead_time = d.pop("lead_time", UNSET)

        linked_drawing_ids = cast(list[int], d.pop("linked_drawing_ids", UNSET))

        def _parse_location_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        location_id = _parse_location_id(d.pop("location_id", UNSET))

        number = d.pop("number", UNSET)

        private = d.pop("private", UNSET)

        _received_date = d.pop("received_date", UNSET)
        received_date: datetime.date | Unset
        if isinstance(_received_date, Unset):
            received_date = UNSET
        else:
            received_date = datetime.date.fromisoformat(_received_date)

        def _parse_received_from(
            data: object,
        ) -> ListSubmittalsResponse200ItemReceivedFromType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                received_from_type_0 = (
                    ListSubmittalsResponse200ItemReceivedFromType0.from_dict(data)
                )

                return received_from_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemReceivedFromType0 | None | Unset, data
            )

        received_from = _parse_received_from(d.pop("received_from", UNSET))

        _required_on_site_date = d.pop("required_on_site_date", UNSET)
        required_on_site_date: datetime.date | Unset
        if isinstance(_required_on_site_date, Unset):
            required_on_site_date = UNSET
        else:
            required_on_site_date = datetime.date.fromisoformat(_required_on_site_date)

        def _parse_responsible_contractor(
            data: object,
        ) -> ListSubmittalsResponse200ItemResponsibleContractorType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                responsible_contractor_type_0 = (
                    ListSubmittalsResponse200ItemResponsibleContractorType0.from_dict(
                        data
                    )
                )

                return responsible_contractor_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemResponsibleContractorType0 | None | Unset,
                data,
            )

        responsible_contractor = _parse_responsible_contractor(
            d.pop("responsible_contractor", UNSET)
        )

        revision = d.pop("revision", UNSET)

        _scheduled_task = d.pop("scheduled_task", UNSET)
        scheduled_task: ListSubmittalsResponse200ItemScheduledTask | Unset
        if isinstance(_scheduled_task, Unset):
            scheduled_task = UNSET
        else:
            scheduled_task = ListSubmittalsResponse200ItemScheduledTask.from_dict(
                _scheduled_task
            )

        def _parse_specification_section(
            data: object,
        ) -> ListSubmittalsResponse200ItemSpecificationSectionType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                specification_section_type_0 = (
                    ListSubmittalsResponse200ItemSpecificationSectionType0.from_dict(
                        data
                    )
                )

                return specification_section_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemSpecificationSectionType0 | None | Unset,
                data,
            )

        specification_section = _parse_specification_section(
            d.pop("specification_section", UNSET)
        )

        _status = d.pop("status", UNSET)
        status: ListSubmittalsResponse200ItemStatus | Unset
        if isinstance(_status, Unset):
            status = UNSET
        else:
            status = ListSubmittalsResponse200ItemStatus.from_dict(_status)

        def _parse_sub_job_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        sub_job_id = _parse_sub_job_id(d.pop("sub_job_id", UNSET))

        _submit_by = d.pop("submit_by", UNSET)
        submit_by: datetime.date | Unset
        if isinstance(_submit_by, Unset):
            submit_by = UNSET
        else:
            submit_by = datetime.date.fromisoformat(_submit_by)

        def _parse_submittal_manager(
            data: object,
        ) -> ListSubmittalsResponse200ItemSubmittalManagerType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                submittal_manager_type_0 = (
                    ListSubmittalsResponse200ItemSubmittalManagerType0.from_dict(data)
                )

                return submittal_manager_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemSubmittalManagerType0 | None | Unset, data
            )

        submittal_manager = _parse_submittal_manager(d.pop("submittal_manager", UNSET))

        def _parse_submittal_package(
            data: object,
        ) -> ListSubmittalsResponse200ItemSubmittalPackageType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                submittal_package_type_0 = (
                    ListSubmittalsResponse200ItemSubmittalPackageType0.from_dict(data)
                )

                return submittal_package_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemSubmittalPackageType0 | None | Unset, data
            )

        submittal_package = _parse_submittal_package(d.pop("submittal_package", UNSET))

        def _parse_submittal_workflow_template(
            data: object,
        ) -> ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                submittal_workflow_template_type_0 = ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0.from_dict(
                    data
                )

                return submittal_workflow_template_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListSubmittalsResponse200ItemSubmittalWorkflowTemplateType0
                | None
                | Unset,
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

        def _parse_type_(
            data: object,
        ) -> ListSubmittalsResponse200ItemTypeType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                type_type_0 = ListSubmittalsResponse200ItemTypeType0.from_dict(data)

                return type_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ListSubmittalsResponse200ItemTypeType0 | None | Unset, data)

        type_ = _parse_type_(d.pop("type", UNSET))

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        list_submittals_response_200_item = cls(
            actual_delivery_date=actual_delivery_date,
            approvers=approvers,
            associated_attachments=associated_attachments,
            ball_in_court=ball_in_court,
            closed_at=closed_at,
            cost_code_id=cost_code_id,
            created_at=created_at,
            created_by=created_by,
            current_revision=current_revision,
            custom_fields=custom_fields,
            description=description,
            distributed_at=distributed_at,
            distribution_members=distribution_members,
            drawing_ids=drawing_ids,
            due_date=due_date,
            formatted_number=formatted_number,
            id=id,
            issue_date=issue_date,
            last_distributed_submittal=last_distributed_submittal,
            lead_time=lead_time,
            linked_drawing_ids=linked_drawing_ids,
            location_id=location_id,
            number=number,
            private=private,
            received_date=received_date,
            received_from=received_from,
            required_on_site_date=required_on_site_date,
            responsible_contractor=responsible_contractor,
            revision=revision,
            scheduled_task=scheduled_task,
            specification_section=specification_section,
            status=status,
            sub_job_id=sub_job_id,
            submit_by=submit_by,
            submittal_manager=submittal_manager,
            submittal_package=submittal_package,
            submittal_workflow_template=submittal_workflow_template,
            submittal_workflow_template_applied_at=submittal_workflow_template_applied_at,
            title=title,
            type_=type_,
            updated_at=updated_at,
        )

        list_submittals_response_200_item.additional_properties = d
        return list_submittals_response_200_item

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
