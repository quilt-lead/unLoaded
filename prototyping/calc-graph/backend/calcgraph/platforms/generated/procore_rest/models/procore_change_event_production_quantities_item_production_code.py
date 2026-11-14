from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.procore_change_event_production_quantities_item_production_code_cost_code import (
        ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode,
    )
    from ..models.procore_change_event_production_quantities_item_production_code_sub_job_type_0 import (
        ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0,
    )
    from ..models.procore_change_event_production_quantities_item_production_code_wbs_code import (
        ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCode,
    )


T = TypeVar("T", bound="ProcoreChangeEventProductionQuantitiesItemProductionCode")


@_attrs_define
class ProcoreChangeEventProductionQuantitiesItemProductionCode:
    """production quantity cost code and if enabled sub job data

    Attributes:
        cost_code (ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode | Unset): cost code data
        sub_job (None | ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0 | Unset): cost code related
            sub job data in case when cost code biller is subjob
        wbs_code (ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCode | Unset): Item's associated Budget
            Code
    """

    cost_code: (
        ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode | Unset
    ) = UNSET
    sub_job: (
        None
        | ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0
        | Unset
    ) = UNSET
    wbs_code: (
        ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCode | Unset
    ) = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.procore_change_event_production_quantities_item_production_code_sub_job_type_0 import (
            ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0,
        )

        cost_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.cost_code, Unset):
            cost_code = self.cost_code.to_dict()

        sub_job: dict[str, Any] | None | Unset
        if isinstance(self.sub_job, Unset):
            sub_job = UNSET
        elif isinstance(
            self.sub_job,
            ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0,
        ):
            sub_job = self.sub_job.to_dict()
        else:
            sub_job = self.sub_job

        wbs_code: dict[str, Any] | Unset = UNSET
        if not isinstance(self.wbs_code, Unset):
            wbs_code = self.wbs_code.to_dict()

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if cost_code is not UNSET:
            field_dict["cost_code"] = cost_code
        if sub_job is not UNSET:
            field_dict["sub_job"] = sub_job
        if wbs_code is not UNSET:
            field_dict["wbs_code"] = wbs_code

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.procore_change_event_production_quantities_item_production_code_cost_code import (
            ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode,
        )
        from ..models.procore_change_event_production_quantities_item_production_code_sub_job_type_0 import (
            ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0,
        )
        from ..models.procore_change_event_production_quantities_item_production_code_wbs_code import (
            ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCode,
        )

        d = dict(src_dict)
        _cost_code = d.pop("cost_code", UNSET)
        cost_code: (
            ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode | Unset
        )
        if isinstance(_cost_code, Unset):
            cost_code = UNSET
        else:
            cost_code = ProcoreChangeEventProductionQuantitiesItemProductionCodeCostCode.from_dict(
                _cost_code
            )

        def _parse_sub_job(
            data: object,
        ) -> (
            None
            | ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                sub_job_type_0 = ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0.from_dict(
                    data
                )

                return sub_job_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                None
                | ProcoreChangeEventProductionQuantitiesItemProductionCodeSubJobType0
                | Unset,
                data,
            )

        sub_job = _parse_sub_job(d.pop("sub_job", UNSET))

        _wbs_code = d.pop("wbs_code", UNSET)
        wbs_code: (
            ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCode | Unset
        )
        if isinstance(_wbs_code, Unset):
            wbs_code = UNSET
        else:
            wbs_code = ProcoreChangeEventProductionQuantitiesItemProductionCodeWbsCode.from_dict(
                _wbs_code
            )

        procore_change_event_production_quantities_item_production_code = cls(
            cost_code=cost_code,
            sub_job=sub_job,
            wbs_code=wbs_code,
        )

        procore_change_event_production_quantities_item_production_code.additional_properties = d
        return procore_change_event_production_quantities_item_production_code

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
