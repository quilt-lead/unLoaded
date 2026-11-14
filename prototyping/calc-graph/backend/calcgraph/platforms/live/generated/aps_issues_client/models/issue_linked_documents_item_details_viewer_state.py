from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

T = TypeVar("T", bound="IssueLinkedDocumentsItemDetailsViewerState")


@_attrs_define
class IssueLinkedDocumentsItemDetailsViewerState:
    """The viewer state at the time the pushpin was created. Maximum length: 2,500,000 characters. You can get the viewer
    state object by calling ViewerState.getState(). To restore the viewer instance use ViewerState.restoreState(). See
    the `Viewer API documentation https://developer.autodesk.com/en/docs/viewer/v2/reference/javascript/viewerstate/`_
    for more details.

    """

    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        issue_linked_documents_item_details_viewer_state = cls()

        issue_linked_documents_item_details_viewer_state.additional_properties = d
        return issue_linked_documents_item_details_viewer_state

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
