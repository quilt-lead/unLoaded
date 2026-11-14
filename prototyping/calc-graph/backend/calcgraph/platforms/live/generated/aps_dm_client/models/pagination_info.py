from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.pagination_info_first import PaginationInfoFirst
    from ..models.pagination_info_next import PaginationInfoNext
    from ..models.pagination_info_prev import PaginationInfoPrev
    from ..models.pagination_info_self import PaginationInfoSelf


T = TypeVar("T", bound="PaginationInfo")


@_attrs_define
class PaginationInfo:
    """An object that is returned with responses that can be split across multiple pages. "Next," "Previous," and "First"
    are available only if the response is split across multiple pages.

        Attributes:
            self_ (PaginationInfoSelf): A container for the link to the current page of the response.
            first (PaginationInfoFirst | Unset): A container for the link to the first page of the response.
            next_ (PaginationInfoNext | Unset): A container for the link to the next page of the response.
            prev (PaginationInfoPrev | Unset): A container for the link to the previous page of the response.
    """

    self_: PaginationInfoSelf
    first: PaginationInfoFirst | Unset = UNSET
    next_: PaginationInfoNext | Unset = UNSET
    prev: PaginationInfoPrev | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        self_ = self.self_.to_dict()

        first: dict[str, Any] | Unset = UNSET
        if not isinstance(self.first, Unset):
            first = self.first.to_dict()

        next_: dict[str, Any] | Unset = UNSET
        if not isinstance(self.next_, Unset):
            next_ = self.next_.to_dict()

        prev: dict[str, Any] | Unset = UNSET
        if not isinstance(self.prev, Unset):
            prev = self.prev.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "self": self_,
            }
        )
        if first is not UNSET:
            field_dict["first"] = first
        if next_ is not UNSET:
            field_dict["next"] = next_
        if prev is not UNSET:
            field_dict["prev"] = prev

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.pagination_info_first import PaginationInfoFirst
        from ..models.pagination_info_next import PaginationInfoNext
        from ..models.pagination_info_prev import PaginationInfoPrev
        from ..models.pagination_info_self import PaginationInfoSelf

        d = dict(src_dict)
        self_ = PaginationInfoSelf.from_dict(d.pop("self"))

        _first = d.pop("first", UNSET)
        first: PaginationInfoFirst | Unset
        if isinstance(_first, Unset):
            first = UNSET
        else:
            first = PaginationInfoFirst.from_dict(_first)

        _next_ = d.pop("next", UNSET)
        next_: PaginationInfoNext | Unset
        if isinstance(_next_, Unset):
            next_ = UNSET
        else:
            next_ = PaginationInfoNext.from_dict(_next_)

        _prev = d.pop("prev", UNSET)
        prev: PaginationInfoPrev | Unset
        if isinstance(_prev, Unset):
            prev = UNSET
        else:
            prev = PaginationInfoPrev.from_dict(_prev)

        pagination_info = cls(
            self_=self_,
            first=first,
            next_=next_,
            prev=prev,
        )

        pagination_info.additional_properties = d
        return pagination_info

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
