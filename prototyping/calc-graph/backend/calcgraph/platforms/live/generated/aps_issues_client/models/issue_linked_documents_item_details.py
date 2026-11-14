from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.issue_linked_documents_item_details_position import (
        IssueLinkedDocumentsItemDetailsPosition,
    )
    from ..models.issue_linked_documents_item_details_viewable import (
        IssueLinkedDocumentsItemDetailsViewable,
    )
    from ..models.issue_linked_documents_item_details_viewer_state import (
        IssueLinkedDocumentsItemDetailsViewerState,
    )


T = TypeVar("T", bound="IssueLinkedDocumentsItemDetails")


@_attrs_define
class IssueLinkedDocumentsItemDetails:
    """Information about the individual viewable.

    Attributes:
        external_id (str | Unset): An external identifier of the element the pushpin is associated with in the viewable.
        object_id (int | Unset): The ID of the element the pushpin is associated with in the viewable.
        position (IssueLinkedDocumentsItemDetailsPosition | Unset): The position of the pushpin in the viewable.
        viewable (IssueLinkedDocumentsItemDetailsViewable | Unset): The individual viewable associated with the issue
            (pushpin). This is relevant for both individual 2D sheets and views within a 3D model, and individual PDF sheets
            within a multi-sheet PDF file. It is only relevant if the issue is associated with a file.
        viewer_state (IssueLinkedDocumentsItemDetailsViewerState | Unset): The viewer state at the time the pushpin was
            created. Maximum length: 2,500,000 characters. You can get the viewer state object by calling
            ViewerState.getState(). To restore the viewer instance use ViewerState.restoreState(). See the `Viewer API
            documentation https://developer.autodesk.com/en/docs/viewer/v2/reference/javascript/viewerstate/`_ for more
            details.
    """

    external_id: str | Unset = UNSET
    object_id: int | Unset = UNSET
    position: IssueLinkedDocumentsItemDetailsPosition | Unset = UNSET
    viewable: IssueLinkedDocumentsItemDetailsViewable | Unset = UNSET
    viewer_state: IssueLinkedDocumentsItemDetailsViewerState | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        external_id = self.external_id

        object_id = self.object_id

        position: dict[str, Any] | Unset = UNSET
        if not isinstance(self.position, Unset):
            position = self.position.to_dict()

        viewable: dict[str, Any] | Unset = UNSET
        if not isinstance(self.viewable, Unset):
            viewable = self.viewable.to_dict()

        viewer_state: dict[str, Any] | Unset = UNSET
        if not isinstance(self.viewer_state, Unset):
            viewer_state = self.viewer_state.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if external_id is not UNSET:
            field_dict["externalId"] = external_id
        if object_id is not UNSET:
            field_dict["objectId"] = object_id
        if position is not UNSET:
            field_dict["position"] = position
        if viewable is not UNSET:
            field_dict["viewable"] = viewable
        if viewer_state is not UNSET:
            field_dict["viewerState"] = viewer_state

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.issue_linked_documents_item_details_position import (
            IssueLinkedDocumentsItemDetailsPosition,
        )
        from ..models.issue_linked_documents_item_details_viewable import (
            IssueLinkedDocumentsItemDetailsViewable,
        )
        from ..models.issue_linked_documents_item_details_viewer_state import (
            IssueLinkedDocumentsItemDetailsViewerState,
        )

        d = dict(src_dict)
        external_id = d.pop("externalId", UNSET)

        object_id = d.pop("objectId", UNSET)

        _position = d.pop("position", UNSET)
        position: IssueLinkedDocumentsItemDetailsPosition | Unset
        if isinstance(_position, Unset):
            position = UNSET
        else:
            position = IssueLinkedDocumentsItemDetailsPosition.from_dict(_position)

        _viewable = d.pop("viewable", UNSET)
        viewable: IssueLinkedDocumentsItemDetailsViewable | Unset
        if isinstance(_viewable, Unset):
            viewable = UNSET
        else:
            viewable = IssueLinkedDocumentsItemDetailsViewable.from_dict(_viewable)

        _viewer_state = d.pop("viewerState", UNSET)
        viewer_state: IssueLinkedDocumentsItemDetailsViewerState | Unset
        if isinstance(_viewer_state, Unset):
            viewer_state = UNSET
        else:
            viewer_state = IssueLinkedDocumentsItemDetailsViewerState.from_dict(
                _viewer_state
            )

        issue_linked_documents_item_details = cls(
            external_id=external_id,
            object_id=object_id,
            position=position,
            viewable=viewable,
            viewer_state=viewer_state,
        )

        issue_linked_documents_item_details.additional_properties = d
        return issue_linked_documents_item_details

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
