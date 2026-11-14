from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.user_issues_filter import UserIssuesFilter
    from ..models.user_issues_new import UserIssuesNew


T = TypeVar("T", bound="UserIssues")


@_attrs_define
class UserIssues:
    """
    Attributes:
        filter_ (UserIssuesFilter | Unset): Not relevant
        new (UserIssuesNew | Unset): If this object appears in the response, it indicates that the user can create and
            modify issues.
    """

    filter_: UserIssuesFilter | Unset = UNSET
    new: UserIssuesNew | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        filter_: dict[str, Any] | Unset = UNSET
        if not isinstance(self.filter_, Unset):
            filter_ = self.filter_.to_dict()

        new: dict[str, Any] | Unset = UNSET
        if not isinstance(self.new, Unset):
            new = self.new.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if filter_ is not UNSET:
            field_dict["filter"] = filter_
        if new is not UNSET:
            field_dict["new"] = new

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.user_issues_filter import UserIssuesFilter
        from ..models.user_issues_new import UserIssuesNew

        d = dict(src_dict)
        _filter_ = d.pop("filter", UNSET)
        filter_: UserIssuesFilter | Unset
        if isinstance(_filter_, Unset):
            filter_ = UNSET
        else:
            filter_ = UserIssuesFilter.from_dict(_filter_)

        _new = d.pop("new", UNSET)
        new: UserIssuesNew | Unset
        if isinstance(_new, Unset):
            new = UNSET
        else:
            new = UserIssuesNew.from_dict(_new)

        user_issues = cls(
            filter_=filter_,
            new=new,
        )

        user_issues.additional_properties = d
        return user_issues

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
