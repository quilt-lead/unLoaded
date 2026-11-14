from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, File, FileTypes, Unset

T = TypeVar("T", bound="CreateRfiBodyRfiQuestion")


@_attrs_define
class CreateRfiBodyRfiQuestion:
    """The Question of the RFI

    Attributes:
        body (str): The Body of the Question
        attachments (list[File] | Unset): RFI Question Attachments. To upload attachments you must upload the entire
            payload as `multipart/form-data` content-type and specify each parameter as form-data together with
            `attachments[]` as files.
        document_management_document_revision_ids (list[str] | Unset): Document Management Document Revisions to attach
            to the response
        drawing_revision_ids (list[int] | Unset): Drawing Revisions to attach to the response
        file_version_ids (list[int] | Unset): File Versions to attach to the response
        form_ids (list[int] | Unset): Forms to attach to the response
        image_ids (list[int] | Unset): Images to attach to the response
        prostore_file_ids (list[int] | Unset): An array of Prostore File IDs. The Prostore Files will be associated with
            the RFI as attachments.
        upload_ids (list[str] | Unset): Uploads to attach to the response
    """

    body: str
    attachments: list[File] | Unset = UNSET
    document_management_document_revision_ids: list[str] | Unset = UNSET
    drawing_revision_ids: list[int] | Unset = UNSET
    file_version_ids: list[int] | Unset = UNSET
    form_ids: list[int] | Unset = UNSET
    image_ids: list[int] | Unset = UNSET
    prostore_file_ids: list[int] | Unset = UNSET
    upload_ids: list[str] | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        body = self.body

        attachments: list[FileTypes] | Unset = UNSET
        if not isinstance(self.attachments, Unset):
            attachments = []
            for attachments_item_data in self.attachments:
                attachments_item = attachments_item_data.to_tuple()

                attachments.append(attachments_item)

        document_management_document_revision_ids: list[str] | Unset = UNSET
        if not isinstance(self.document_management_document_revision_ids, Unset):
            document_management_document_revision_ids = (
                self.document_management_document_revision_ids
            )

        drawing_revision_ids: list[int] | Unset = UNSET
        if not isinstance(self.drawing_revision_ids, Unset):
            drawing_revision_ids = self.drawing_revision_ids

        file_version_ids: list[int] | Unset = UNSET
        if not isinstance(self.file_version_ids, Unset):
            file_version_ids = self.file_version_ids

        form_ids: list[int] | Unset = UNSET
        if not isinstance(self.form_ids, Unset):
            form_ids = self.form_ids

        image_ids: list[int] | Unset = UNSET
        if not isinstance(self.image_ids, Unset):
            image_ids = self.image_ids

        prostore_file_ids: list[int] | Unset = UNSET
        if not isinstance(self.prostore_file_ids, Unset):
            prostore_file_ids = self.prostore_file_ids

        upload_ids: list[str] | Unset = UNSET
        if not isinstance(self.upload_ids, Unset):
            upload_ids = self.upload_ids

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update(
            {
                "body": body,
            }
        )
        if attachments is not UNSET:
            field_dict["attachments"] = attachments
        if document_management_document_revision_ids is not UNSET:
            field_dict["document_management_document_revision_ids"] = (
                document_management_document_revision_ids
            )
        if drawing_revision_ids is not UNSET:
            field_dict["drawing_revision_ids"] = drawing_revision_ids
        if file_version_ids is not UNSET:
            field_dict["file_version_ids"] = file_version_ids
        if form_ids is not UNSET:
            field_dict["form_ids"] = form_ids
        if image_ids is not UNSET:
            field_dict["image_ids"] = image_ids
        if prostore_file_ids is not UNSET:
            field_dict["prostore_file_ids"] = prostore_file_ids
        if upload_ids is not UNSET:
            field_dict["upload_ids"] = upload_ids

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        d = dict(src_dict)
        body = d.pop("body")

        _attachments = d.pop("attachments", UNSET)
        attachments: list[File] | Unset = UNSET
        if _attachments is not UNSET:
            attachments = []
            for attachments_item_data in _attachments:
                attachments_item = File(payload=BytesIO(attachments_item_data))

                attachments.append(attachments_item)

        document_management_document_revision_ids = cast(
            list[str], d.pop("document_management_document_revision_ids", UNSET)
        )

        drawing_revision_ids = cast(list[int], d.pop("drawing_revision_ids", UNSET))

        file_version_ids = cast(list[int], d.pop("file_version_ids", UNSET))

        form_ids = cast(list[int], d.pop("form_ids", UNSET))

        image_ids = cast(list[int], d.pop("image_ids", UNSET))

        prostore_file_ids = cast(list[int], d.pop("prostore_file_ids", UNSET))

        upload_ids = cast(list[str], d.pop("upload_ids", UNSET))

        create_rfi_body_rfi_question = cls(
            body=body,
            attachments=attachments,
            document_management_document_revision_ids=document_management_document_revision_ids,
            drawing_revision_ids=drawing_revision_ids,
            file_version_ids=file_version_ids,
            form_ids=form_ids,
            image_ids=image_ids,
            prostore_file_ids=prostore_file_ids,
            upload_ids=upload_ids,
        )

        create_rfi_body_rfi_question.additional_properties = d
        return create_rfi_body_rfi_question

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
