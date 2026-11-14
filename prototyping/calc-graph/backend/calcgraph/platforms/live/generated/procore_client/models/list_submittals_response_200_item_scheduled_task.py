from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

T = TypeVar("T", bound="ListSubmittalsResponse200ItemScheduledTask")


@_attrs_define
class ListSubmittalsResponse200ItemScheduledTask:
    """Information about the scheduled task associated with this submittal

    Attributes:
        finish_date (datetime.datetime | Unset): the finish date of the scheduled task
        formatted_name (str | Unset): formatted name of the scheduled task
        id (int | Unset): Scheduled Task ID
        key (str | Unset): surrogate key of the scheduled task
        name (str | Unset): Full Name of the scheduled task
        start_date (datetime.datetime | Unset): the start date of the scheduled task
        task_name (str | Unset): the raw name of the scheduled task
    """

    finish_date: datetime.datetime | Unset = UNSET
    formatted_name: str | Unset = UNSET
    id: int | Unset = UNSET
    key: str | Unset = UNSET
    name: str | Unset = UNSET
    start_date: datetime.datetime | Unset = UNSET
    task_name: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        finish_date: str | Unset = UNSET
        if not isinstance(self.finish_date, Unset):
            finish_date = self.finish_date.isoformat()

        formatted_name = self.formatted_name

        id = self.id

        key = self.key

        name = self.name

        start_date: str | Unset = UNSET
        if not isinstance(self.start_date, Unset):
            start_date = self.start_date.isoformat()

        task_name = self.task_name

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if finish_date is not UNSET:
            field_dict["finish_date"] = finish_date
        if formatted_name is not UNSET:
            field_dict["formatted_name"] = formatted_name
        if id is not UNSET:
            field_dict["id"] = id
        if key is not UNSET:
            field_dict["key"] = key
        if name is not UNSET:
            field_dict["name"] = name
        if start_date is not UNSET:
            field_dict["start_date"] = start_date
        if task_name is not UNSET:
            field_dict["task_name"] = task_name

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        _finish_date = d.pop("finish_date", UNSET)
        finish_date: datetime.datetime | Unset
        if isinstance(_finish_date, Unset):
            finish_date = UNSET
        else:
            finish_date = datetime.datetime.fromisoformat(_finish_date)

        formatted_name = d.pop("formatted_name", UNSET)

        id = d.pop("id", UNSET)

        key = d.pop("key", UNSET)

        name = d.pop("name", UNSET)

        _start_date = d.pop("start_date", UNSET)
        start_date: datetime.datetime | Unset
        if isinstance(_start_date, Unset):
            start_date = UNSET
        else:
            start_date = datetime.datetime.fromisoformat(_start_date)

        task_name = d.pop("task_name", UNSET)

        list_submittals_response_200_item_scheduled_task = cls(
            finish_date=finish_date,
            formatted_name=formatted_name,
            id=id,
            key=key,
            name=name,
            start_date=start_date,
            task_name=task_name,
        )

        list_submittals_response_200_item_scheduled_task.additional_properties = d
        return list_submittals_response_200_item_scheduled_task

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
