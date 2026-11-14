from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.create_rfi_body_rfi_cost_impact import CreateRfiBodyRfiCostImpact
    from ..models.create_rfi_body_rfi_question import CreateRfiBodyRfiQuestion
    from ..models.create_rfi_body_rfi_schedule_impact import (
        CreateRfiBodyRfiScheduleImpact,
    )


T = TypeVar("T", bound="CreateRfiBodyRfi")


@_attrs_define
class CreateRfiBodyRfi:
    """
    Attributes:
        question (CreateRfiBodyRfiQuestion): The Question of the RFI
        rfi_manager_id (int): The ID of the RFI Manager User of the RFI
            *Only admin users (or standard users, if the project's configuration allows for it) can set this field
        subject (str): The Subject of the RFI
        assignee_id (int | Unset): The ID of the Assignee User.
            *Only admin users can set this field
            DEPRECATED. Please use assignee_ids instead
        assignee_ids (list[int] | Unset): An array of IDs of the Assignees of the RFI
            *Only admin users can set this field
            **If this param is not provided, the assigned_id will be used instead
        cost_code_id (int | Unset): The ID of the Cost Code of the RFI
        cost_impact (CreateRfiBodyRfiCostImpact | Unset): The Cost Impact of the RFI
        custom_textfield_1 (str | Unset): The Custom Textfield 1 of the RFI
        custom_textfield_2 (str | Unset): The Custom Textfield 2 of the RFI
        distribution_ids (list[int] | Unset): An array of IDs of the Distributions of the RFI
        draft (bool | Unset): The Draft status of the RFI Default: False.
        drawing_number (str | Unset): The Drawing Number of the RFI
        due_date (datetime.date | Unset): The Due Date of the RFI
            *Only admin users can set this field
        location_id (int | Unset): The ID of the Location of the RFI
        number (str | Unset): The Number of the RFI
            *This field will be auto-populated if the RFI is not draft
            **When creating a new revision of an RFI, if not provided, it will inherit the number from the source RFI.
        private (bool | Unset): The Private status of the RFI Default: False.
        project_stage_id (int | Unset): The ID of the Project Stage of the RFI
            *If Number By Stage is enabled in RFI settings, this will add the prefix of the project stage to the full number
            of the RFI.
            **This field is not needed when creating a new revision of an RFI, as it will inherit the project stage from the
            source RFI.
        received_from_login_information_id (int | Unset): The ID of the Received From User of the RFI
        reference (str | Unset): The Reference of the RFI
        required_assignee_ids (list[int] | Unset): An array of IDs of the Assignees that are required to respond to the
            RFI * Only admin users can set this field ** IDs must also be present in assignee_ids
        responsible_contractor_id (int | Unset): The ID of the Responsible Contractor Vendor of the RFI
        revision (str | Unset): Revision Number
            *This field is required only when creating a new revision of an RFI.
        schedule_impact (CreateRfiBodyRfiScheduleImpact | Unset): The Schedule Impact of the RFI
        source_rfi_header_id (int | Unset): The ID of The Root RFI Revision
            *This field is required only when creating a new revision of an RFI.
        specification_section_id (int | Unset): The ID of the Specification Section of the RFI
    """

    question: CreateRfiBodyRfiQuestion
    rfi_manager_id: int
    subject: str
    assignee_id: int | Unset = UNSET
    assignee_ids: list[int] | Unset = UNSET
    cost_code_id: int | Unset = UNSET
    cost_impact: CreateRfiBodyRfiCostImpact | Unset = UNSET
    custom_textfield_1: str | Unset = UNSET
    custom_textfield_2: str | Unset = UNSET
    distribution_ids: list[int] | Unset = UNSET
    draft: bool | Unset = False
    drawing_number: str | Unset = UNSET
    due_date: datetime.date | Unset = UNSET
    location_id: int | Unset = UNSET
    number: str | Unset = UNSET
    private: bool | Unset = False
    project_stage_id: int | Unset = UNSET
    received_from_login_information_id: int | Unset = UNSET
    reference: str | Unset = UNSET
    required_assignee_ids: list[int] | Unset = UNSET
    responsible_contractor_id: int | Unset = UNSET
    revision: str | Unset = UNSET
    schedule_impact: CreateRfiBodyRfiScheduleImpact | Unset = UNSET
    source_rfi_header_id: int | Unset = UNSET
    specification_section_id: int | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        question = self.question.to_dict()

        rfi_manager_id = self.rfi_manager_id

        subject = self.subject

        assignee_id = self.assignee_id

        assignee_ids: list[int] | Unset = UNSET
        if not isinstance(self.assignee_ids, Unset):
            assignee_ids = self.assignee_ids

        cost_code_id = self.cost_code_id

        cost_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_impact, Unset):
            cost_impact = self.cost_impact.to_dict()

        custom_textfield_1 = self.custom_textfield_1

        custom_textfield_2 = self.custom_textfield_2

        distribution_ids: list[int] | Unset = UNSET
        if not isinstance(self.distribution_ids, Unset):
            distribution_ids = self.distribution_ids

        draft = self.draft

        drawing_number = self.drawing_number

        due_date: str | Unset = UNSET
        if not isinstance(self.due_date, Unset):
            due_date = self.due_date.isoformat()

        location_id = self.location_id

        number = self.number

        private = self.private

        project_stage_id = self.project_stage_id

        received_from_login_information_id = self.received_from_login_information_id

        reference = self.reference

        required_assignee_ids: list[int] | Unset = UNSET
        if not isinstance(self.required_assignee_ids, Unset):
            required_assignee_ids = self.required_assignee_ids

        responsible_contractor_id = self.responsible_contractor_id

        revision = self.revision

        schedule_impact: dict[str, Any] | Unset = UNSET
        if not isinstance(self.schedule_impact, Unset):
            schedule_impact = self.schedule_impact.to_dict()

        source_rfi_header_id = self.source_rfi_header_id

        specification_section_id = self.specification_section_id

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "question": question,
                "rfi_manager_id": rfi_manager_id,
                "subject": subject,
            }
        )
        if assignee_id is not UNSET:
            field_dict["assignee_id"] = assignee_id
        if assignee_ids is not UNSET:
            field_dict["assignee_ids"] = assignee_ids
        if cost_code_id is not UNSET:
            field_dict["cost_code_id"] = cost_code_id
        if cost_impact is not UNSET:
            field_dict["cost_impact"] = cost_impact
        if custom_textfield_1 is not UNSET:
            field_dict["custom_textfield_1"] = custom_textfield_1
        if custom_textfield_2 is not UNSET:
            field_dict["custom_textfield_2"] = custom_textfield_2
        if distribution_ids is not UNSET:
            field_dict["distribution_ids"] = distribution_ids
        if draft is not UNSET:
            field_dict["draft"] = draft
        if drawing_number is not UNSET:
            field_dict["drawing_number"] = drawing_number
        if due_date is not UNSET:
            field_dict["due_date"] = due_date
        if location_id is not UNSET:
            field_dict["location_id"] = location_id
        if number is not UNSET:
            field_dict["number"] = number
        if private is not UNSET:
            field_dict["private"] = private
        if project_stage_id is not UNSET:
            field_dict["project_stage_id"] = project_stage_id
        if received_from_login_information_id is not UNSET:
            field_dict["received_from_login_information_id"] = (
                received_from_login_information_id
            )
        if reference is not UNSET:
            field_dict["reference"] = reference
        if required_assignee_ids is not UNSET:
            field_dict["required_assignee_ids"] = required_assignee_ids
        if responsible_contractor_id is not UNSET:
            field_dict["responsible_contractor_id"] = responsible_contractor_id
        if revision is not UNSET:
            field_dict["revision"] = revision
        if schedule_impact is not UNSET:
            field_dict["schedule_impact"] = schedule_impact
        if source_rfi_header_id is not UNSET:
            field_dict["source_rfi_header_id"] = source_rfi_header_id
        if specification_section_id is not UNSET:
            field_dict["specification_section_id"] = specification_section_id

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.create_rfi_body_rfi_cost_impact import CreateRfiBodyRfiCostImpact
        from ..models.create_rfi_body_rfi_question import CreateRfiBodyRfiQuestion
        from ..models.create_rfi_body_rfi_schedule_impact import (
            CreateRfiBodyRfiScheduleImpact,
        )

        d = dict(src_dict)
        question = CreateRfiBodyRfiQuestion.from_dict(d.pop("question"))

        rfi_manager_id = d.pop("rfi_manager_id")

        subject = d.pop("subject")

        assignee_id = d.pop("assignee_id", UNSET)

        assignee_ids = cast(list[int], d.pop("assignee_ids", UNSET))

        cost_code_id = d.pop("cost_code_id", UNSET)

        _cost_impact = d.pop("cost_impact", UNSET)
        cost_impact: CreateRfiBodyRfiCostImpact | Unset
        if isinstance(_cost_impact, Unset):
            cost_impact = UNSET
        else:
            cost_impact = CreateRfiBodyRfiCostImpact.from_dict(_cost_impact)

        custom_textfield_1 = d.pop("custom_textfield_1", UNSET)

        custom_textfield_2 = d.pop("custom_textfield_2", UNSET)

        distribution_ids = cast(list[int], d.pop("distribution_ids", UNSET))

        draft = d.pop("draft", UNSET)

        drawing_number = d.pop("drawing_number", UNSET)

        _due_date = d.pop("due_date", UNSET)
        due_date: datetime.date | Unset
        if isinstance(_due_date, Unset):
            due_date = UNSET
        else:
            due_date = datetime.date.fromisoformat(_due_date)

        location_id = d.pop("location_id", UNSET)

        number = d.pop("number", UNSET)

        private = d.pop("private", UNSET)

        project_stage_id = d.pop("project_stage_id", UNSET)

        received_from_login_information_id = d.pop(
            "received_from_login_information_id", UNSET
        )

        reference = d.pop("reference", UNSET)

        required_assignee_ids = cast(list[int], d.pop("required_assignee_ids", UNSET))

        responsible_contractor_id = d.pop("responsible_contractor_id", UNSET)

        revision = d.pop("revision", UNSET)

        _schedule_impact = d.pop("schedule_impact", UNSET)
        schedule_impact: CreateRfiBodyRfiScheduleImpact | Unset
        if isinstance(_schedule_impact, Unset):
            schedule_impact = UNSET
        else:
            schedule_impact = CreateRfiBodyRfiScheduleImpact.from_dict(_schedule_impact)

        source_rfi_header_id = d.pop("source_rfi_header_id", UNSET)

        specification_section_id = d.pop("specification_section_id", UNSET)

        create_rfi_body_rfi = cls(
            question=question,
            rfi_manager_id=rfi_manager_id,
            subject=subject,
            assignee_id=assignee_id,
            assignee_ids=assignee_ids,
            cost_code_id=cost_code_id,
            cost_impact=cost_impact,
            custom_textfield_1=custom_textfield_1,
            custom_textfield_2=custom_textfield_2,
            distribution_ids=distribution_ids,
            draft=draft,
            drawing_number=drawing_number,
            due_date=due_date,
            location_id=location_id,
            number=number,
            private=private,
            project_stage_id=project_stage_id,
            received_from_login_information_id=received_from_login_information_id,
            reference=reference,
            required_assignee_ids=required_assignee_ids,
            responsible_contractor_id=responsible_contractor_id,
            revision=revision,
            schedule_impact=schedule_impact,
            source_rfi_header_id=source_rfi_header_id,
            specification_section_id=specification_section_id,
        )

        create_rfi_body_rfi.additional_properties = d
        return create_rfi_body_rfi

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
