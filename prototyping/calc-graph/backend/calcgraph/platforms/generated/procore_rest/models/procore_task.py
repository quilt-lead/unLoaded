from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_task_created_by import ProcoreTaskCreatedBy
    from ..models.procore_task_updated_by import ProcoreTaskUpdatedBy


T = TypeVar("T", bound="ProcoreTask")


@_attrs_define
class ProcoreTask:
    """
    Attributes:
        activity_id (str | Unset): The external unique identifier for this task. Note that due to an
            oversight in the original API, the value returned for this attribute
            will be the `source_uid` value supplied when creating a task.
        actual_finish (datetime.datetime | Unset): Actual finish timestamp for this task in ISO 8601 UTC format.
        actual_start (datetime.datetime | Unset): Actual start timestamp for this task in ISO 8601 UTC format.
        baseline_finish (datetime.datetime | Unset): The baseline finish timestamp for this task in ISO 8601 UTC format.
        baseline_start (datetime.datetime | Unset): The baseline start timestamp for this task in ISO 8601 UTC format.
        color (str | Unset): The RGB color value, expressed in hex digits for the color used when
            displaying the task in Procore. The color varies depending on whether
            the task is on the critical path, complete, unstarted or in progress.
        created_at (datetime.datetime | Unset): Date/time the Task was created in ISO 8601 UTC format.
        created_by (ProcoreTaskCreatedBy | Unset):
        critical_path (bool | Unset): True if this task is on the critical path.
        finish_datetime (datetime.datetime | Unset): Task finish timestamp in ISO 8601 UTC format.
        finish_variance (float | Unset): The finish variance in days for this task.
        full_outline_path (str | Unset): Task full outline path
        has_children (bool | Unset): True if this is a summary task, i.e. this task has child tasks.
        id (int | Unset): Unique identifier for this task.
        key (str | Unset): A deprecated value which was originally used to uniquely identify tasks.
            This value will be removed in a later version of the API.
        manually_edited (bool | Unset): Set to true if the task has been created or modified in Procore, false
            if the task was imported from an external schedule and has not been
            modified in Procore.
        milestone (bool | Unset): True if this task is a milestone.
        name (str | Unset): Task name as the user sees it in Procore. Depending on the project settings this may include
            the full outline path
        notes (str | Unset): Arbitrary notes about this task.
        parent_id (int | Unset): ID of the parent task.
        pending (bool | Unset): True if one or more change requests are pending for this task.
        percentage (int | Unset): Percent complete value for this task.
        resource_ids (list[int] | Unset): The resources assigned to this task, represented as an array of
            resource ID values.
        resource_name (str | Unset): Names of any resources assigned to this task.
        row_number (int | Unset): The row number of a task defines the sequence in which tasks are normally
            expected to be displayed.
        schedule_activity_id (str | Unset): For tasks imported from external systems which have the concept of
            an "Activity ID" (for example Primavera P6), this attribute is
            used to hold the Activity ID value. Note that due to an oversight
            during the creation of this API, this is the value supplied
            in the `activity_id` attribute. This will be corrected in a later
            version of the API.
        schedule_duration (float | Unset): The duration of this task in days as defined by the external system
            which owns the schedule data.
        source_uid (str | Unset): The unique identifier for this task from the external system which
            owns the schedule data.
        start_datetime (datetime.datetime | Unset): Task start timestamp in ISO 8601 UTC format.
        start_variance (float | Unset): The start variance in days for this task.
        task_name (str | Unset): Task name. This will always contain just the task name, and will not include the full
            outline path.
        updated_at (datetime.datetime | Unset): Date/time the Task was last updated in ISO 8601 UTC format.
        updated_by (ProcoreTaskUpdatedBy | Unset):
        wbs (str | Unset): Work Breakdown Structure (WBS) number for this task.
    """

    activity_id: str | Unset = UNSET
    actual_finish: datetime.datetime | Unset = UNSET
    actual_start: datetime.datetime | Unset = UNSET
    baseline_finish: datetime.datetime | Unset = UNSET
    baseline_start: datetime.datetime | Unset = UNSET
    color: str | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: ProcoreTaskCreatedBy | Unset = UNSET
    critical_path: bool | Unset = UNSET
    finish_datetime: datetime.datetime | Unset = UNSET
    finish_variance: float | Unset = UNSET
    full_outline_path: str | Unset = UNSET
    has_children: bool | Unset = UNSET
    id: int | Unset = UNSET
    key: str | Unset = UNSET
    manually_edited: bool | Unset = UNSET
    milestone: bool | Unset = UNSET
    name: str | Unset = UNSET
    notes: str | Unset = UNSET
    parent_id: int | Unset = UNSET
    pending: bool | Unset = UNSET
    percentage: int | Unset = UNSET
    resource_ids: list[int] | Unset = UNSET
    resource_name: str | Unset = UNSET
    row_number: int | Unset = UNSET
    schedule_activity_id: str | Unset = UNSET
    schedule_duration: float | Unset = UNSET
    source_uid: str | Unset = UNSET
    start_datetime: datetime.datetime | Unset = UNSET
    start_variance: float | Unset = UNSET
    task_name: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    updated_by: ProcoreTaskUpdatedBy | Unset = UNSET
    wbs: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        activity_id = self.activity_id

        actual_finish: str | Unset = UNSET
        if not isinstance(self.actual_finish, Unset):
            actual_finish = self.actual_finish.isoformat()

        actual_start: str | Unset = UNSET
        if not isinstance(self.actual_start, Unset):
            actual_start = self.actual_start.isoformat()

        baseline_finish: str | Unset = UNSET
        if not isinstance(self.baseline_finish, Unset):
            baseline_finish = self.baseline_finish.isoformat()

        baseline_start: str | Unset = UNSET
        if not isinstance(self.baseline_start, Unset):
            baseline_start = self.baseline_start.isoformat()

        color = self.color

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        created_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.created_by, Unset):
            created_by = self.created_by.to_dict()

        critical_path = self.critical_path

        finish_datetime: str | Unset = UNSET
        if not isinstance(self.finish_datetime, Unset):
            finish_datetime = self.finish_datetime.isoformat()

        finish_variance = self.finish_variance

        full_outline_path = self.full_outline_path

        has_children = self.has_children

        id = self.id

        key = self.key

        manually_edited = self.manually_edited

        milestone = self.milestone

        name = self.name

        notes = self.notes

        parent_id = self.parent_id

        pending = self.pending

        percentage = self.percentage

        resource_ids: list[int] | Unset = UNSET
        if not isinstance(self.resource_ids, Unset):
            resource_ids = self.resource_ids

        resource_name = self.resource_name

        row_number = self.row_number

        schedule_activity_id = self.schedule_activity_id

        schedule_duration = self.schedule_duration

        source_uid = self.source_uid

        start_datetime: str | Unset = UNSET
        if not isinstance(self.start_datetime, Unset):
            start_datetime = self.start_datetime.isoformat()

        start_variance = self.start_variance

        task_name = self.task_name

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        updated_by: dict[str, Any] | Unset = UNSET
        if not isinstance(self.updated_by, Unset):
            updated_by = self.updated_by.to_dict()

        wbs = self.wbs

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if activity_id is not UNSET:
            field_dict["activity_id"] = activity_id
        if actual_finish is not UNSET:
            field_dict["actual_finish"] = actual_finish
        if actual_start is not UNSET:
            field_dict["actual_start"] = actual_start
        if baseline_finish is not UNSET:
            field_dict["baseline_finish"] = baseline_finish
        if baseline_start is not UNSET:
            field_dict["baseline_start"] = baseline_start
        if color is not UNSET:
            field_dict["color"] = color
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if critical_path is not UNSET:
            field_dict["critical_path"] = critical_path
        if finish_datetime is not UNSET:
            field_dict["finish_datetime"] = finish_datetime
        if finish_variance is not UNSET:
            field_dict["finish_variance"] = finish_variance
        if full_outline_path is not UNSET:
            field_dict["full_outline_path"] = full_outline_path
        if has_children is not UNSET:
            field_dict["has_children"] = has_children
        if id is not UNSET:
            field_dict["id"] = id
        if key is not UNSET:
            field_dict["key"] = key
        if manually_edited is not UNSET:
            field_dict["manually_edited"] = manually_edited
        if milestone is not UNSET:
            field_dict["milestone"] = milestone
        if name is not UNSET:
            field_dict["name"] = name
        if notes is not UNSET:
            field_dict["notes"] = notes
        if parent_id is not UNSET:
            field_dict["parent_id"] = parent_id
        if pending is not UNSET:
            field_dict["pending"] = pending
        if percentage is not UNSET:
            field_dict["percentage"] = percentage
        if resource_ids is not UNSET:
            field_dict["resource_ids"] = resource_ids
        if resource_name is not UNSET:
            field_dict["resource_name"] = resource_name
        if row_number is not UNSET:
            field_dict["row_number"] = row_number
        if schedule_activity_id is not UNSET:
            field_dict["schedule_activity_id"] = schedule_activity_id
        if schedule_duration is not UNSET:
            field_dict["schedule_duration"] = schedule_duration
        if source_uid is not UNSET:
            field_dict["source_uid"] = source_uid
        if start_datetime is not UNSET:
            field_dict["start_datetime"] = start_datetime
        if start_variance is not UNSET:
            field_dict["start_variance"] = start_variance
        if task_name is not UNSET:
            field_dict["task_name"] = task_name
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at
        if updated_by is not UNSET:
            field_dict["updated_by"] = updated_by
        if wbs is not UNSET:
            field_dict["wbs"] = wbs

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_task_created_by import ProcoreTaskCreatedBy
        from ..models.procore_task_updated_by import ProcoreTaskUpdatedBy

        d = dict(src_dict)
        activity_id = d.pop("activity_id", UNSET)

        _actual_finish = d.pop("actual_finish", UNSET)
        actual_finish: datetime.datetime | Unset
        if isinstance(_actual_finish, Unset):
            actual_finish = UNSET
        else:
            actual_finish = datetime.datetime.fromisoformat(_actual_finish)

        _actual_start = d.pop("actual_start", UNSET)
        actual_start: datetime.datetime | Unset
        if isinstance(_actual_start, Unset):
            actual_start = UNSET
        else:
            actual_start = datetime.datetime.fromisoformat(_actual_start)

        _baseline_finish = d.pop("baseline_finish", UNSET)
        baseline_finish: datetime.datetime | Unset
        if isinstance(_baseline_finish, Unset):
            baseline_finish = UNSET
        else:
            baseline_finish = datetime.datetime.fromisoformat(_baseline_finish)

        _baseline_start = d.pop("baseline_start", UNSET)
        baseline_start: datetime.datetime | Unset
        if isinstance(_baseline_start, Unset):
            baseline_start = UNSET
        else:
            baseline_start = datetime.datetime.fromisoformat(_baseline_start)

        color = d.pop("color", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        _created_by = d.pop("created_by", UNSET)
        created_by: ProcoreTaskCreatedBy | Unset
        if isinstance(_created_by, Unset):
            created_by = UNSET
        else:
            created_by = ProcoreTaskCreatedBy.from_dict(_created_by)

        critical_path = d.pop("critical_path", UNSET)

        _finish_datetime = d.pop("finish_datetime", UNSET)
        finish_datetime: datetime.datetime | Unset
        if isinstance(_finish_datetime, Unset):
            finish_datetime = UNSET
        else:
            finish_datetime = datetime.datetime.fromisoformat(_finish_datetime)

        finish_variance = d.pop("finish_variance", UNSET)

        full_outline_path = d.pop("full_outline_path", UNSET)

        has_children = d.pop("has_children", UNSET)

        id = d.pop("id", UNSET)

        key = d.pop("key", UNSET)

        manually_edited = d.pop("manually_edited", UNSET)

        milestone = d.pop("milestone", UNSET)

        name = d.pop("name", UNSET)

        notes = d.pop("notes", UNSET)

        parent_id = d.pop("parent_id", UNSET)

        pending = d.pop("pending", UNSET)

        percentage = d.pop("percentage", UNSET)

        resource_ids = cast(list[int], d.pop("resource_ids", UNSET))

        resource_name = d.pop("resource_name", UNSET)

        row_number = d.pop("row_number", UNSET)

        schedule_activity_id = d.pop("schedule_activity_id", UNSET)

        schedule_duration = d.pop("schedule_duration", UNSET)

        source_uid = d.pop("source_uid", UNSET)

        _start_datetime = d.pop("start_datetime", UNSET)
        start_datetime: datetime.datetime | Unset
        if isinstance(_start_datetime, Unset):
            start_datetime = UNSET
        else:
            start_datetime = datetime.datetime.fromisoformat(_start_datetime)

        start_variance = d.pop("start_variance", UNSET)

        task_name = d.pop("task_name", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        _updated_by = d.pop("updated_by", UNSET)
        updated_by: ProcoreTaskUpdatedBy | Unset
        if isinstance(_updated_by, Unset):
            updated_by = UNSET
        else:
            updated_by = ProcoreTaskUpdatedBy.from_dict(_updated_by)

        wbs = d.pop("wbs", UNSET)

        procore_task = cls(
            activity_id=activity_id,
            actual_finish=actual_finish,
            actual_start=actual_start,
            baseline_finish=baseline_finish,
            baseline_start=baseline_start,
            color=color,
            created_at=created_at,
            created_by=created_by,
            critical_path=critical_path,
            finish_datetime=finish_datetime,
            finish_variance=finish_variance,
            full_outline_path=full_outline_path,
            has_children=has_children,
            id=id,
            key=key,
            manually_edited=manually_edited,
            milestone=milestone,
            name=name,
            notes=notes,
            parent_id=parent_id,
            pending=pending,
            percentage=percentage,
            resource_ids=resource_ids,
            resource_name=resource_name,
            row_number=row_number,
            schedule_activity_id=schedule_activity_id,
            schedule_duration=schedule_duration,
            source_uid=source_uid,
            start_datetime=start_datetime,
            start_variance=start_variance,
            task_name=task_name,
            updated_at=updated_at,
            updated_by=updated_by,
            wbs=wbs,
        )

        procore_task.additional_properties = d
        return procore_task

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
