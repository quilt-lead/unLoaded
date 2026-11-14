from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.json_api_link import JsonApiLink
    from ..models.web_view_link import WebViewLink


T = TypeVar("T", bound="JsonApiLinksSelfAndWebView")


@_attrs_define
class JsonApiLinksSelfAndWebView:
    """Information on links to this resource.

    Attributes:
        self_ (JsonApiLink): An object containing the hyperlink to the referenced resource.
        web_view (WebViewLink | Unset): An object containing a link that opens the resource in a browser.
    """

    self_: JsonApiLink
    web_view: WebViewLink | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        self_ = self.self_.to_dict()

        web_view: dict[str, Any] | Unset = UNSET
        if not isinstance(self.web_view, Unset):
            web_view = self.web_view.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "self": self_,
            }
        )
        if web_view is not UNSET:
            field_dict["webView"] = web_view

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.json_api_link import JsonApiLink
        from ..models.web_view_link import WebViewLink

        d = dict(src_dict)
        self_ = JsonApiLink.from_dict(d.pop("self"))

        _web_view = d.pop("webView", UNSET)
        web_view: WebViewLink | Unset
        if isinstance(_web_view, Unset):
            web_view = UNSET
        else:
            web_view = WebViewLink.from_dict(_web_view)

        json_api_links_self_and_web_view = cls(
            self_=self_,
            web_view=web_view,
        )

        json_api_links_self_and_web_view.additional_properties = d
        return json_api_links_self_and_web_view

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
