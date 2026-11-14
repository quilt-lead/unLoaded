from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.create_submittal_body_submittal_lead_time_format import (
    CreateSubmittalBodySubmittalLeadTimeFormat,
)
from ..types import UNSET, Unset

T = TypeVar("T", bound="CreateSubmittalBodySubmittal")


@_attrs_define
class CreateSubmittalBodySubmittal:
    """
    Attributes:
        number (str): The Number of the Submittal
        actual_delivery_date (datetime.date | Unset): The Actual Delivery Date of the Submittal
            *This field can only be set if the project has submittal delivery information enabled
        buffer_time (int | Unset): The buffer working days for the dynamic submittal plan calculation *This field is
            only available to be set if Dynamic Submittal Plan is enabled
        confirmed_delivery_date (datetime.date | Unset): The Confirmed Delivery Date of the Submittal
            *This field can only be set if the project has submittal delivery information enabled
        cost_code_id (int | Unset): The ID of the Cost Code of the Submittal
            *This field can only be set by admins
        custom_textarea_1 (str | Unset): Value for the project's custom submittal textarea field (label configured in
            Submittals Settings).
            *This field can only be set by admins
        custom_textfield_1 (str | Unset): Value for the project's custom submittal text field (label configured in
            Submittals Settings).
            *This field can only be set by admins
        description (str | Unset): The Description of the Submittal
        design_team_review_time (int | Unset): The Design Team Review Time of the Submittal (in days)
            *This field can only be set if the project has schedule calculations enabled
        distribution_member_ids (list[int] | Unset): The IDs of the Distribution Members of the Submittal
        due_date (datetime.date | Unset): The Due Date of the Submittal
            *This field is not available to be set if sequential approvers is enabled
        for_record_only (bool | Unset): The field that controls if the dynamic submittal plan is for record only or not
            *This field is only available to be set if Dynamic Submittal Plan is enabled
        formatted_lead_time (str | Unset): Human-readable lead time string, interpreted together with
            `lead_time_format`.
        internal_review_time (int | Unset): The Internal Review Time of the Submtital (in days)
            *This field can only be set if the project has schedule calculations enabled
        is_rejected (bool | Unset): Whether the Submittal is marked as rejected. *This field applies to submittal update
            only.
        issue_date (datetime.date | Unset): The Issue Date of the Submittal
            *This field can only be set by admins
        lead_time (int | Unset): The Lead Time of the Submittal (in days)
            *This field can only be set by admins or if the project has schedule calculations enabled
        lead_time_format (CreateSubmittalBodySubmittalLeadTimeFormat | Unset): The unit format used to interpret the
            lead time value.
        location_id (int | Unset): The Location of the Submittal
        prepare_time (int | Unset): The prepare time, in working days, for the dynamic submittal plan calculation. *This
            field is only available to be set if Dynamic Submittal Plan is enabled
        private (bool | Unset): Whether the Submittal is Private or not
        prostore_file_ids (list[int] | Unset): An array of Prostore File IDs. The Prostore Files will be associated with
            the Submittal as attachments.
        received_date (datetime.date | Unset): The Received Date of the Submittal
            *This field can only be set by admins
        received_from_id (int | Unset): The Received From of the Submittal
        rejected_submittal_log_approver_id (int | Unset): The ID of the approver whose response rejected the Submittal.
            *This field applies to submittal update only.
        required_on_site_date (datetime.date | Unset): The Required On Site Date of the Submittal
            *This field can only be set by admins or if the project has schedule calculations enabled
        responsible_contractor_id (int | Unset): The Responsible Contractor of the Submittal
            *This field is required when received_from_id is present and the field is visible in the project's field
            configuration
        revision (str | Unset): The Revision of the Submittal
        scheduled_task_id (int | Unset): The ID of the Scheduled Task of the Submittal
            *This field can only be set if the project has submittal delivery information enabled and the user has
            permissions to view the calendar tool
        scheduled_task_key (str | Unset): The key of the Scheduled Task of the Submittal. Note that use of this
            parameter is deprecated. Please use `scheduled_task_id` instead.
            *This field can only be set if the project has submittal delivery information enabled and the user has
            permissions to view the calendar tool
        source_submittal_log_id (int | Unset): The ID of the Source Submittal.
            *By setting this field, the submittal will be created as a revision of source submittal.
        source_submittal_revision_id (int | Unset): The ID of the Submittal Log revision to copy revision attributes
            from when creating a new revision; `source_submittal_log_id` must be set when using this parameter. *This field
            only applies when creating a submittal as a revision of an existing submittal and is not supported on submittal
            update via PATCH.
        specification_section_id (int | Unset): The ID of the Specification Section of the Submittal
        status_id (int | Unset): The ID of the Submittal Status of the Submittal
            *This field can only be set by admins
        sub_job_id (int | Unset): The ID of the Sub Job of the Submittal
        submit_by (datetime.date | Unset): The Submit By Date of the Submittal
            *This field can only be set by admins
        submit_by_date_overridden (bool | Unset): Whether the Submit By date was manually overridden rather than
            calculated from the schedule.
        submittal_manager_id (int | Unset): The ID of the Submittal Manager of the Submittal
            *This field can only be set by admins
        submittal_package_id (int | Unset): The ID of the Submittal Package of the Submittal
            *This field can only be set by admins
        submittal_workflow_template_id (int | Unset): The ID of a Submittal Workflow Template to apply to the
            submittal's approval workflow.
        title (str | Unset): The Title of the Submittal
        type_ (str | Unset): The Submittal Type of the Submittal
    """

    number: str
    actual_delivery_date: datetime.date | Unset = UNSET
    buffer_time: int | Unset = UNSET
    confirmed_delivery_date: datetime.date | Unset = UNSET
    cost_code_id: int | Unset = UNSET
    custom_textarea_1: str | Unset = UNSET
    custom_textfield_1: str | Unset = UNSET
    description: str | Unset = UNSET
    design_team_review_time: int | Unset = UNSET
    distribution_member_ids: list[int] | Unset = UNSET
    due_date: datetime.date | Unset = UNSET
    for_record_only: bool | Unset = UNSET
    formatted_lead_time: str | Unset = UNSET
    internal_review_time: int | Unset = UNSET
    is_rejected: bool | Unset = UNSET
    issue_date: datetime.date | Unset = UNSET
    lead_time: int | Unset = UNSET
    lead_time_format: CreateSubmittalBodySubmittalLeadTimeFormat | Unset = UNSET
    location_id: int | Unset = UNSET
    prepare_time: int | Unset = UNSET
    private: bool | Unset = UNSET
    prostore_file_ids: list[int] | Unset = UNSET
    received_date: datetime.date | Unset = UNSET
    received_from_id: int | Unset = UNSET
    rejected_submittal_log_approver_id: int | Unset = UNSET
    required_on_site_date: datetime.date | Unset = UNSET
    responsible_contractor_id: int | Unset = UNSET
    revision: str | Unset = UNSET
    scheduled_task_id: int | Unset = UNSET
    scheduled_task_key: str | Unset = UNSET
    source_submittal_log_id: int | Unset = UNSET
    source_submittal_revision_id: int | Unset = UNSET
    specification_section_id: int | Unset = UNSET
    status_id: int | Unset = UNSET
    sub_job_id: int | Unset = UNSET
    submit_by: datetime.date | Unset = UNSET
    submit_by_date_overridden: bool | Unset = UNSET
    submittal_manager_id: int | Unset = UNSET
    submittal_package_id: int | Unset = UNSET
    submittal_workflow_template_id: int | Unset = UNSET
    title: str | Unset = UNSET
    type_: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        number = self.number

        actual_delivery_date: str | Unset = UNSET
        if not isinstance(self.actual_delivery_date, Unset):
            actual_delivery_date = self.actual_delivery_date.isoformat()

        buffer_time = self.buffer_time

        confirmed_delivery_date: str | Unset = UNSET
        if not isinstance(self.confirmed_delivery_date, Unset):
            confirmed_delivery_date = self.confirmed_delivery_date.isoformat()

        cost_code_id = self.cost_code_id

        custom_textarea_1 = self.custom_textarea_1

        custom_textfield_1 = self.custom_textfield_1

        description = self.description

        design_team_review_time = self.design_team_review_time

        distribution_member_ids: list[int] | Unset = UNSET
        if not isinstance(self.distribution_member_ids, Unset):
            distribution_member_ids = self.distribution_member_ids

        due_date: str | Unset = UNSET
        if not isinstance(self.due_date, Unset):
            due_date = self.due_date.isoformat()

        for_record_only = self.for_record_only

        formatted_lead_time = self.formatted_lead_time

        internal_review_time = self.internal_review_time

        is_rejected = self.is_rejected

        issue_date: str | Unset = UNSET
        if not isinstance(self.issue_date, Unset):
            issue_date = self.issue_date.isoformat()

        lead_time = self.lead_time

        lead_time_format: str | Unset = UNSET
        if not isinstance(self.lead_time_format, Unset):
            lead_time_format = self.lead_time_format.value

        location_id = self.location_id

        prepare_time = self.prepare_time

        private = self.private

        prostore_file_ids: list[int] | Unset = UNSET
        if not isinstance(self.prostore_file_ids, Unset):
            prostore_file_ids = self.prostore_file_ids

        received_date: str | Unset = UNSET
        if not isinstance(self.received_date, Unset):
            received_date = self.received_date.isoformat()

        received_from_id = self.received_from_id

        rejected_submittal_log_approver_id = self.rejected_submittal_log_approver_id

        required_on_site_date: str | Unset = UNSET
        if not isinstance(self.required_on_site_date, Unset):
            required_on_site_date = self.required_on_site_date.isoformat()

        responsible_contractor_id = self.responsible_contractor_id

        revision = self.revision

        scheduled_task_id = self.scheduled_task_id

        scheduled_task_key = self.scheduled_task_key

        source_submittal_log_id = self.source_submittal_log_id

        source_submittal_revision_id = self.source_submittal_revision_id

        specification_section_id = self.specification_section_id

        status_id = self.status_id

        sub_job_id = self.sub_job_id

        submit_by: str | Unset = UNSET
        if not isinstance(self.submit_by, Unset):
            submit_by = self.submit_by.isoformat()

        submit_by_date_overridden = self.submit_by_date_overridden

        submittal_manager_id = self.submittal_manager_id

        submittal_package_id = self.submittal_package_id

        submittal_workflow_template_id = self.submittal_workflow_template_id

        title = self.title

        type_ = self.type_

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "number": number,
            }
        )
        if actual_delivery_date is not UNSET:
            field_dict["actual_delivery_date"] = actual_delivery_date
        if buffer_time is not UNSET:
            field_dict["buffer_time"] = buffer_time
        if confirmed_delivery_date is not UNSET:
            field_dict["confirmed_delivery_date"] = confirmed_delivery_date
        if cost_code_id is not UNSET:
            field_dict["cost_code_id"] = cost_code_id
        if custom_textarea_1 is not UNSET:
            field_dict["custom_textarea_1"] = custom_textarea_1
        if custom_textfield_1 is not UNSET:
            field_dict["custom_textfield_1"] = custom_textfield_1
        if description is not UNSET:
            field_dict["description"] = description
        if design_team_review_time is not UNSET:
            field_dict["design_team_review_time"] = design_team_review_time
        if distribution_member_ids is not UNSET:
            field_dict["distribution_member_ids"] = distribution_member_ids
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if for_record_only is not UNSET:
            field_dict["for_record_only"] = for_record_only
        if formatted_lead_time is not UNSET:
            field_dict["formatted_lead_time"] = formatted_lead_time
        if internal_review_time is not UNSET:
            field_dict["internal_review_time"] = internal_review_time
        if is_rejected is not UNSET:
            field_dict["is_rejected"] = is_rejected
        if issue_date is not UNSET:
            field_dict["issue_date"] = issue_date
        if lead_time is not UNSET:
            field_dict["lead_time"] = lead_time
        if lead_time_format is not UNSET:
            field_dict["lead_time_format"] = lead_time_format
        if location_id is not UNSET:
            field_dict["location_id"] = location_id
        if prepare_time is not UNSET:
            field_dict["prepare_time"] = prepare_time
        if private is not UNSET:
            field_dict["private"] = private
        if prostore_file_ids is not UNSET:
            field_dict["prostore_file_ids"] = prostore_file_ids
        if received_date is not UNSET:
            field_dict["received_date"] = received_date
        if received_from_id is not UNSET:
            field_dict["received_from_id"] = received_from_id
        if rejected_submittal_log_approver_id is not UNSET:
            field_dict["rejected_submittal_log_approver_id"] = (
                rejected_submittal_log_approver_id
            )
        if required_on_site_date is not UNSET:
            field_dict["required_on_site_date"] = required_on_site_date
        if responsible_contractor_id is not UNSET:
            field_dict["responsible_contractor_id"] = responsible_contractor_id
        if revision is not UNSET:
            field_dict["revision"] = revision
        if scheduled_task_id is not UNSET:
            field_dict["scheduled_task_id"] = scheduled_task_id
        if scheduled_task_key is not UNSET:
            field_dict["scheduled_task_key"] = scheduled_task_key
        if source_submittal_log_id is not UNSET:
            field_dict["source_submittal_log_id"] = source_submittal_log_id
        if source_submittal_revision_id is not UNSET:
            field_dict["source_submittal_revision_id"] = source_submittal_revision_id
        if specification_section_id is not UNSET:
            field_dict["specification_section_id"] = specification_section_id
        if status_id is not UNSET:
            field_dict["status_id"] = status_id
        if sub_job_id is not UNSET:
            field_dict["sub_job_id"] = sub_job_id
        if submit_by is not UNSET:
            field_dict["submit_by"] = submit_by
        if submit_by_date_overridden is not UNSET:
            field_dict["submit_by_date_overridden"] = submit_by_date_overridden
        if submittal_manager_id is not UNSET:
            field_dict["submittal_manager_id"] = submittal_manager_id
        if submittal_package_id is not UNSET:
            field_dict["submittal_package_id"] = submittal_package_id
        if submittal_workflow_template_id is not UNSET:
            field_dict["submittal_workflow_template_id"] = (
                submittal_workflow_template_id
            )
        if title is not UNSET:
            field_dict["title"] = title
        if type_ is not UNSET:
            field_dict["type"] = type_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        number = d.pop("number")

        _actual_delivery_date = d.pop("actual_delivery_date", UNSET)
        actual_delivery_date: datetime.date | Unset
        if isinstance(_actual_delivery_date, Unset):
            actual_delivery_date = UNSET
        else:
            actual_delivery_date = datetime.date.fromisoformat(_actual_delivery_date)

        buffer_time = d.pop("buffer_time", UNSET)

        _confirmed_delivery_date = d.pop("confirmed_delivery_date", UNSET)
        confirmed_delivery_date: datetime.date | Unset
        if isinstance(_confirmed_delivery_date, Unset):
            confirmed_delivery_date = UNSET
        else:
            confirmed_delivery_date = datetime.date.fromisoformat(
                _confirmed_delivery_date
            )

        cost_code_id = d.pop("cost_code_id", UNSET)

        custom_textarea_1 = d.pop("custom_textarea_1", UNSET)

        custom_textfield_1 = d.pop("custom_textfield_1", UNSET)

        description = d.pop("description", UNSET)

        design_team_review_time = d.pop("design_team_review_time", UNSET)

        distribution_member_ids = cast(
            list[int], d.pop("distribution_member_ids", UNSET)
        )

        _due_date = d.pop("due_date", UNSET)
        due_date: datetime.date | Unset
        if isinstance(_due_date, Unset):
            due_date = UNSET
        else:
            due_date = datetime.date.fromisoformat(_due_date)

        for_record_only = d.pop("for_record_only", UNSET)

        formatted_lead_time = d.pop("formatted_lead_time", UNSET)

        internal_review_time = d.pop("internal_review_time", UNSET)

        is_rejected = d.pop("is_rejected", UNSET)

        _issue_date = d.pop("issue_date", UNSET)
        issue_date: datetime.date | Unset
        if isinstance(_issue_date, Unset):
            issue_date = UNSET
        else:
            issue_date = datetime.date.fromisoformat(_issue_date)

        lead_time = d.pop("lead_time", UNSET)

        _lead_time_format = d.pop("lead_time_format", UNSET)
        lead_time_format: CreateSubmittalBodySubmittalLeadTimeFormat | Unset
        if isinstance(_lead_time_format, Unset):
            lead_time_format = UNSET
        else:
            lead_time_format = CreateSubmittalBodySubmittalLeadTimeFormat(
                _lead_time_format
            )

        location_id = d.pop("location_id", UNSET)

        prepare_time = d.pop("prepare_time", UNSET)

        private = d.pop("private", UNSET)

        prostore_file_ids = cast(list[int], d.pop("prostore_file_ids", UNSET))

        _received_date = d.pop("received_date", UNSET)
        received_date: datetime.date | Unset
        if isinstance(_received_date, Unset):
            received_date = UNSET
        else:
            received_date = datetime.date.fromisoformat(_received_date)

        received_from_id = d.pop("received_from_id", UNSET)

        rejected_submittal_log_approver_id = d.pop(
            "rejected_submittal_log_approver_id", UNSET
        )

        _required_on_site_date = d.pop("required_on_site_date", UNSET)
        required_on_site_date: datetime.date | Unset
        if isinstance(_required_on_site_date, Unset):
            required_on_site_date = UNSET
        else:
            required_on_site_date = datetime.date.fromisoformat(_required_on_site_date)

        responsible_contractor_id = d.pop("responsible_contractor_id", UNSET)

        revision = d.pop("revision", UNSET)

        scheduled_task_id = d.pop("scheduled_task_id", UNSET)

        scheduled_task_key = d.pop("scheduled_task_key", UNSET)

        source_submittal_log_id = d.pop("source_submittal_log_id", UNSET)

        source_submittal_revision_id = d.pop("source_submittal_revision_id", UNSET)

        specification_section_id = d.pop("specification_section_id", UNSET)

        status_id = d.pop("status_id", UNSET)

        sub_job_id = d.pop("sub_job_id", UNSET)

        _submit_by = d.pop("submit_by", UNSET)
        submit_by: datetime.date | Unset
        if isinstance(_submit_by, Unset):
            submit_by = UNSET
        else:
            submit_by = datetime.date.fromisoformat(_submit_by)

        submit_by_date_overridden = d.pop("submit_by_date_overridden", UNSET)

        submittal_manager_id = d.pop("submittal_manager_id", UNSET)

        submittal_package_id = d.pop("submittal_package_id", UNSET)

        submittal_workflow_template_id = d.pop("submittal_workflow_template_id", UNSET)

        title = d.pop("title", UNSET)

        type_ = d.pop("type", UNSET)

        create_submittal_body_submittal = cls(
            number=number,
            actual_delivery_date=actual_delivery_date,
            buffer_time=buffer_time,
            confirmed_delivery_date=confirmed_delivery_date,
            cost_code_id=cost_code_id,
            custom_textarea_1=custom_textarea_1,
            custom_textfield_1=custom_textfield_1,
            description=description,
            design_team_review_time=design_team_review_time,
            distribution_member_ids=distribution_member_ids,
            due_date=due_date,
            for_record_only=for_record_only,
            formatted_lead_time=formatted_lead_time,
            internal_review_time=internal_review_time,
            is_rejected=is_rejected,
            issue_date=issue_date,
            lead_time=lead_time,
            lead_time_format=lead_time_format,
            location_id=location_id,
            prepare_time=prepare_time,
            private=private,
            prostore_file_ids=prostore_file_ids,
            received_date=received_date,
            received_from_id=received_from_id,
            rejected_submittal_log_approver_id=rejected_submittal_log_approver_id,
            required_on_site_date=required_on_site_date,
            responsible_contractor_id=responsible_contractor_id,
            revision=revision,
            scheduled_task_id=scheduled_task_id,
            scheduled_task_key=scheduled_task_key,
            source_submittal_log_id=source_submittal_log_id,
            source_submittal_revision_id=source_submittal_revision_id,
            specification_section_id=specification_section_id,
            status_id=status_id,
            sub_job_id=sub_job_id,
            submit_by=submit_by,
            submit_by_date_overridden=submit_by_date_overridden,
            submittal_manager_id=submittal_manager_id,
            submittal_package_id=submittal_package_id,
            submittal_workflow_template_id=submittal_workflow_template_id,
            title=title,
            type_=type_,
        )

        create_submittal_body_submittal.additional_properties = d
        return create_submittal_body_submittal

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
