from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_drawing_current_revision_type_0 import (
        ProcoreDrawingCurrentRevisionType0,
    )


T = TypeVar("T", bound="ProcoreDrawing")


@_attrs_define
class ProcoreDrawing:
    """Drawing

    Attributes:
        current_revision (None | ProcoreDrawingCurrentRevisionType0 | Unset): Current drawing revision
        discipline (str | Unset): Drawing discipline
        drawing_discipline_id (int | Unset): Drawing discipline ID
        drawing_number (str | Unset): Canonical drawing number without sheet-number suffix formatting
        id (int | Unset): Drawing ID
        number (str | Unset): Drawing number
        obsolete (bool | Unset): Obsolete status
        sheet_number (int | None | Unset): Sheet number when assigned for multi-sheet drawings
        title (None | str | Unset): Drawing title
    """

    current_revision: None | ProcoreDrawingCurrentRevisionType0 | Unset = UNSET
    discipline: str | Unset = UNSET
    drawing_discipline_id: int | Unset = UNSET
    drawing_number: str | Unset = UNSET
    id: int | Unset = UNSET
    number: str | Unset = UNSET
    obsolete: bool | Unset = UNSET
    sheet_number: int | None | Unset = UNSET
    title: None | str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.procore_drawing_current_revision_type_0 import (
            ProcoreDrawingCurrentRevisionType0,
        )

        current_revision: dict[str, Any] | None | Unset
        if isinstance(self.current_revision, Unset):
            current_revision = UNSET
        elif isinstance(self.current_revision, ProcoreDrawingCurrentRevisionType0):
            current_revision = self.current_revision.to_dict()
        else:
            current_revision = self.current_revision

        discipline = self.discipline

        drawing_discipline_id = self.drawing_discipline_id

        drawing_number = self.drawing_number

        id = self.id

        number = self.number

        obsolete = self.obsolete

        sheet_number: int | None | Unset
        if isinstance(self.sheet_number, Unset):
            sheet_number = UNSET
        else:
            sheet_number = self.sheet_number

        title: None | str | Unset
        if isinstance(self.title, Unset):
            title = UNSET
        else:
            title = self.title

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if current_revision is not UNSET:
            field_dict["current_revision"] = current_revision
        if discipline is not UNSET:
            field_dict["discipline"] = discipline
        if drawing_discipline_id is not UNSET:
            field_dict["drawing_discipline_id"] = drawing_discipline_id
        if drawing_number is not UNSET:
            field_dict["drawing_number"] = drawing_number
        if id is not UNSET:
            field_dict["id"] = id
        if number is not UNSET:
            field_dict["number"] = number
        if obsolete is not UNSET:
            field_dict["obsolete"] = obsolete
        if sheet_number is not UNSET:
            field_dict["sheet_number"] = sheet_number
        if title is not UNSET:
            field_dict["title"] = title

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_drawing_current_revision_type_0 import (
            ProcoreDrawingCurrentRevisionType0,
        )

        d = dict(src_dict)

        def _parse_current_revision(
            data: object,
        ) -> None | ProcoreDrawingCurrentRevisionType0 | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                current_revision_type_0 = ProcoreDrawingCurrentRevisionType0.from_dict(
                    data
                )

                return current_revision_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | ProcoreDrawingCurrentRevisionType0 | Unset, data)

        current_revision = _parse_current_revision(d.pop("current_revision", UNSET))

        discipline = d.pop("discipline", UNSET)

        drawing_discipline_id = d.pop("drawing_discipline_id", UNSET)

        drawing_number = d.pop("drawing_number", UNSET)

        id = d.pop("id", UNSET)

        number = d.pop("number", UNSET)

        obsolete = d.pop("obsolete", UNSET)

        def _parse_sheet_number(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        sheet_number = _parse_sheet_number(d.pop("sheet_number", UNSET))

        def _parse_title(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        title = _parse_title(d.pop("title", UNSET))

        procore_drawing = cls(
            current_revision=current_revision,
            discipline=discipline,
            drawing_discipline_id=drawing_discipline_id,
            drawing_number=drawing_number,
            id=id,
            number=number,
            obsolete=obsolete,
            sheet_number=sheet_number,
            title=title,
        )

        procore_drawing.additional_properties = d
        return procore_drawing

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
