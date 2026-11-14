from __future__ import annotations

import datetime
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar, cast
from uuid import UUID

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..models.list_projects_response_200_item_delivery_method_type_1 import (
    ListProjectsResponse200ItemDeliveryMethodType1,
)
from ..models.list_projects_response_200_item_delivery_method_type_2_type_1 import (
    ListProjectsResponse200ItemDeliveryMethodType2Type1,
)
from ..models.list_projects_response_200_item_delivery_method_type_3_type_1 import (
    ListProjectsResponse200ItemDeliveryMethodType3Type1,
)
from ..models.list_projects_response_200_item_priority import (
    ListProjectsResponse200ItemPriority,
)
from ..models.list_projects_response_200_item_sector_type_1 import (
    ListProjectsResponse200ItemSectorType1,
)
from ..models.list_projects_response_200_item_sector_type_2_type_1 import (
    ListProjectsResponse200ItemSectorType2Type1,
)
from ..models.list_projects_response_200_item_sector_type_3_type_1 import (
    ListProjectsResponse200ItemSectorType3Type1,
)
from ..models.list_projects_response_200_item_work_scope_type_1 import (
    ListProjectsResponse200ItemWorkScopeType1,
)
from ..models.list_projects_response_200_item_work_scope_type_2_type_1 import (
    ListProjectsResponse200ItemWorkScopeType2Type1,
)
from ..models.list_projects_response_200_item_work_scope_type_3_type_1 import (
    ListProjectsResponse200ItemWorkScopeType3Type1,
)
from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.list_projects_response_200_item_company import (
        ListProjectsResponse200ItemCompany,
    )
    from ..models.list_projects_response_200_item_created_by_type_0 import (
        ListProjectsResponse200ItemCreatedByType0,
    )
    from ..models.list_projects_response_200_item_custom_fields import (
        ListProjectsResponse200ItemCustomFields,
    )
    from ..models.list_projects_response_200_item_project_stage import (
        ListProjectsResponse200ItemProjectStage,
    )
    from ..models.list_projects_response_200_item_project_template import (
        ListProjectsResponse200ItemProjectTemplate,
    )
    from ..models.list_projects_response_200_item_project_type import (
        ListProjectsResponse200ItemProjectType,
    )


T = TypeVar("T", bound="ListProjectsResponse200Item")


@_attrs_define
class ListProjectsResponse200Item:
    """
    Attributes:
        accounting_project_number (str | Unset): The accounting project number for the Project
        active (bool | Unset): The active status for the Project
        actual_start_date (datetime.date | Unset): Project actual start date
        address (str | Unset): The street address for the Project
        city (str | Unset): The city in which the Project is located
        code (None | str | Unset): Project code.
        company (ListProjectsResponse200ItemCompany | Unset):
        completion_date (datetime.date | Unset): The completion date for the project
        country_code (str | Unset): The country code for the Project (ISO-3166 Alpha-2 format)
        county (str | Unset): The county in which the Project is located
        created_at (datetime.datetime | Unset): The date and time the Project was created
        created_by (ListProjectsResponse200ItemCreatedByType0 | None | Unset): Login Information
        custom_fields (ListProjectsResponse200ItemCustomFields | Unset):
        delivery_method (ListProjectsResponse200ItemDeliveryMethodType1 |
            ListProjectsResponse200ItemDeliveryMethodType2Type1 | ListProjectsResponse200ItemDeliveryMethodType3Type1 | None
            | Unset): The delivery method of a project.
        description (None | str | Unset): Project description
        designated_market_area (str | Unset): The designated market area the Project is located in
        display_name (str | Unset): The display name for the Project
        erp_integrated (bool | Unset): Whether the project is integrated with ERP.
        estimated_budget (float | None | Unset): Estimated budget for the project.
        estimated_value (str | Unset): The Estimated Value of the project. Note: this field is now deprecated and will
            mirror the value of total_value until it is no longer supported.
        fax (None | str | Unset): Fax number for the project.
        id (int | Unset): Unique identifier for the project.
        is_demo (bool | Unset): Indicates whether this is a test project or not
        latitude (float | Unset): The geographic coordinate that specifies the north–south position of the Project on
            the Earth's surface.
        longitude (float | Unset): The geographic coordinate that specifies the east–west position of the Project on the
            Earth's surface.
        name (str | Unset): The name of the Project
        origin_code (None | str | Unset): An external third-party code associated with the Project
        origin_data (None | str | Unset): An external third-party data string associated with the Project
        origin_id (None | str | Unset): An external third-party identifier for the Project
        owners_project_id (int | None | Unset): A linked identifier for the Owner's Project
        parent_job_id (int | None | Unset): Identifier for the parent job
        phone (str | Unset): The telephone number for the Project
        photo_id (int | None | Unset): The unique identifier for the Project Photo
        portfolio_program_uuid (None | Unset | UUID): UUID of the Portfolio Program assigned to the project. Null when
            unassigned.
        priority (ListProjectsResponse200ItemPriority | Unset): Priority level for the project.
        project_bid_type_id (int | None | Unset): The Bid Type identifier for the Project
        project_number (str | Unset): The Project number
        project_owner_type_id (int | None | Unset): The Owner Type identifier for the Project
        project_region_id (int | None | Unset): The region identifier for the Project
        project_sector_id (int | None | Unset): ID of the project sector associated with the project.
        project_stage (ListProjectsResponse200ItemProjectStage | Unset):
        project_template (ListProjectsResponse200ItemProjectTemplate | Unset): Project template association. Not
            returned by the normal list view.
        project_type (ListProjectsResponse200ItemProjectType | Unset):
        projected_finish_date (datetime.date | None | Unset): Project finish date
        sector (ListProjectsResponse200ItemSectorType1 | ListProjectsResponse200ItemSectorType2Type1 |
            ListProjectsResponse200ItemSectorType3Type1 | None | Unset): The sector of a project.
        square_feet (int | None | Unset): The total square footage for the Project
        start_date (datetime.date | Unset): The start date for the project
        state_code (str | Unset): The state code for the Project (ISO-3166 Alpha-2 format)
        store_number (str | Unset): The store number for the Project
        time_zone (str | Unset): The timezone the Project is located in
        total_value (str | Unset): The total amount of construction work performed, planned, or put in place during the
            project. Note: this field is a replacement to estimated_value and will mirror its value.
        updated_at (datetime.datetime | Unset): The date and time the Project was last updated
        work_scope (ListProjectsResponse200ItemWorkScopeType1 | ListProjectsResponse200ItemWorkScopeType2Type1 |
            ListProjectsResponse200ItemWorkScopeType3Type1 | None | Unset): The work scope of a project.
        zip_ (str | Unset): The postal code for the Project
    """

    accounting_project_number: str | Unset = UNSET
    active: bool | Unset = UNSET
    actual_start_date: datetime.date | Unset = UNSET
    address: str | Unset = UNSET
    city: str | Unset = UNSET
    code: None | str | Unset = UNSET
    company: ListProjectsResponse200ItemCompany | Unset = UNSET
    completion_date: datetime.date | Unset = UNSET
    country_code: str | Unset = UNSET
    county: str | Unset = UNSET
    created_at: datetime.datetime | Unset = UNSET
    created_by: ListProjectsResponse200ItemCreatedByType0 | None | Unset = UNSET
    custom_fields: ListProjectsResponse200ItemCustomFields | Unset = UNSET
    delivery_method: (
        ListProjectsResponse200ItemDeliveryMethodType1
        | ListProjectsResponse200ItemDeliveryMethodType2Type1
        | ListProjectsResponse200ItemDeliveryMethodType3Type1
        | None
        | Unset
    ) = UNSET
    description: None | str | Unset = UNSET
    designated_market_area: str | Unset = UNSET
    display_name: str | Unset = UNSET
    erp_integrated: bool | Unset = UNSET
    estimated_budget: float | None | Unset = UNSET
    estimated_value: str | Unset = UNSET
    fax: None | str | Unset = UNSET
    id: int | Unset = UNSET
    is_demo: bool | Unset = UNSET
    latitude: float | Unset = UNSET
    longitude: float | Unset = UNSET
    name: str | Unset = UNSET
    origin_code: None | str | Unset = UNSET
    origin_data: None | str | Unset = UNSET
    origin_id: None | str | Unset = UNSET
    owners_project_id: int | None | Unset = UNSET
    parent_job_id: int | None | Unset = UNSET
    phone: str | Unset = UNSET
    photo_id: int | None | Unset = UNSET
    portfolio_program_uuid: None | Unset | UUID = UNSET
    priority: ListProjectsResponse200ItemPriority | Unset = UNSET
    project_bid_type_id: int | None | Unset = UNSET
    project_number: str | Unset = UNSET
    project_owner_type_id: int | None | Unset = UNSET
    project_region_id: int | None | Unset = UNSET
    project_sector_id: int | None | Unset = UNSET
    project_stage: ListProjectsResponse200ItemProjectStage | Unset = UNSET
    project_template: ListProjectsResponse200ItemProjectTemplate | Unset = UNSET
    project_type: ListProjectsResponse200ItemProjectType | Unset = UNSET
    projected_finish_date: datetime.date | None | Unset = UNSET
    sector: (
        ListProjectsResponse200ItemSectorType1
        | ListProjectsResponse200ItemSectorType2Type1
        | ListProjectsResponse200ItemSectorType3Type1
        | None
        | Unset
    ) = UNSET
    square_feet: int | None | Unset = UNSET
    start_date: datetime.date | Unset = UNSET
    state_code: str | Unset = UNSET
    store_number: str | Unset = UNSET
    time_zone: str | Unset = UNSET
    total_value: str | Unset = UNSET
    updated_at: datetime.datetime | Unset = UNSET
    work_scope: (
        ListProjectsResponse200ItemWorkScopeType1
        | ListProjectsResponse200ItemWorkScopeType2Type1
        | ListProjectsResponse200ItemWorkScopeType3Type1
        | None
        | Unset
    ) = UNSET
    zip_: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        from ..models.list_projects_response_200_item_created_by_type_0 import (
            ListProjectsResponse200ItemCreatedByType0,
        )

        accounting_project_number = self.accounting_project_number

        active = self.active

        actual_start_date: str | Unset = UNSET
        if not isinstance(self.actual_start_date, Unset):
            actual_start_date = self.actual_start_date.isoformat()

        address = self.address

        city = self.city

        code: None | str | Unset
        if isinstance(self.code, Unset):
            code = UNSET
        else:
            code = self.code

        company: dict[str, Any] | Unset = UNSET
        if not isinstance(self.company, Unset):
            company = self.company.to_dict()

        completion_date: str | Unset = UNSET
        if not isinstance(self.completion_date, Unset):
            completion_date = self.completion_date.isoformat()

        country_code = self.country_code

        county = self.county

        created_at: str | Unset = UNSET
        if not isinstance(self.created_at, Unset):
            created_at = self.created_at.isoformat()

        created_by: dict[str, Any] | None | Unset
        if isinstance(self.created_by, Unset):
            created_by = UNSET
        elif isinstance(self.created_by, ListProjectsResponse200ItemCreatedByType0):
            created_by = self.created_by.to_dict()
        else:
            created_by = self.created_by

        custom_fields: dict[str, Any] | Unset = UNSET
        if not isinstance(self.custom_fields, Unset):
            custom_fields = self.custom_fields.to_dict()

        delivery_method: None | str | Unset
        if isinstance(self.delivery_method, Unset):
            delivery_method = UNSET
        elif (
            isinstance(
                self.delivery_method, ListProjectsResponse200ItemDeliveryMethodType1
            )
            or isinstance(
                self.delivery_method,
                ListProjectsResponse200ItemDeliveryMethodType2Type1,
            )
            or isinstance(
                self.delivery_method,
                ListProjectsResponse200ItemDeliveryMethodType3Type1,
            )
        ):
            delivery_method = self.delivery_method.value
        else:
            delivery_method = self.delivery_method

        description: None | str | Unset
        if isinstance(self.description, Unset):
            description = UNSET
        else:
            description = self.description

        designated_market_area = self.designated_market_area

        display_name = self.display_name

        erp_integrated = self.erp_integrated

        estimated_budget: float | None | Unset
        if isinstance(self.estimated_budget, Unset):
            estimated_budget = UNSET
        else:
            estimated_budget = self.estimated_budget

        estimated_value = self.estimated_value

        fax: None | str | Unset
        if isinstance(self.fax, Unset):
            fax = UNSET
        else:
            fax = self.fax

        id = self.id

        is_demo = self.is_demo

        latitude = self.latitude

        longitude = self.longitude

        name = self.name

        origin_code: None | str | Unset
        if isinstance(self.origin_code, Unset):
            origin_code = UNSET
        else:
            origin_code = self.origin_code

        origin_data: None | str | Unset
        if isinstance(self.origin_data, Unset):
            origin_data = UNSET
        else:
            origin_data = self.origin_data

        origin_id: None | str | Unset
        if isinstance(self.origin_id, Unset):
            origin_id = UNSET
        else:
            origin_id = self.origin_id

        owners_project_id: int | None | Unset
        if isinstance(self.owners_project_id, Unset):
            owners_project_id = UNSET
        else:
            owners_project_id = self.owners_project_id

        parent_job_id: int | None | Unset
        if isinstance(self.parent_job_id, Unset):
            parent_job_id = UNSET
        else:
            parent_job_id = self.parent_job_id

        phone = self.phone

        photo_id: int | None | Unset
        if isinstance(self.photo_id, Unset):
            photo_id = UNSET
        else:
            photo_id = self.photo_id

        portfolio_program_uuid: None | str | Unset
        if isinstance(self.portfolio_program_uuid, Unset):
            portfolio_program_uuid = UNSET
        elif isinstance(self.portfolio_program_uuid, UUID):
            portfolio_program_uuid = str(self.portfolio_program_uuid)
        else:
            portfolio_program_uuid = self.portfolio_program_uuid

        priority: str | Unset = UNSET
        if not isinstance(self.priority, Unset):
            priority = self.priority.value

        project_bid_type_id: int | None | Unset
        if isinstance(self.project_bid_type_id, Unset):
            project_bid_type_id = UNSET
        else:
            project_bid_type_id = self.project_bid_type_id

        project_number = self.project_number

        project_owner_type_id: int | None | Unset
        if isinstance(self.project_owner_type_id, Unset):
            project_owner_type_id = UNSET
        else:
            project_owner_type_id = self.project_owner_type_id

        project_region_id: int | None | Unset
        if isinstance(self.project_region_id, Unset):
            project_region_id = UNSET
        else:
            project_region_id = self.project_region_id

        project_sector_id: int | None | Unset
        if isinstance(self.project_sector_id, Unset):
            project_sector_id = UNSET
        else:
            project_sector_id = self.project_sector_id

        project_stage: dict[str, Any] | Unset = UNSET
        if not isinstance(self.project_stage, Unset):
            project_stage = self.project_stage.to_dict()

        project_template: dict[str, Any] | Unset = UNSET
        if not isinstance(self.project_template, Unset):
            project_template = self.project_template.to_dict()

        project_type: dict[str, Any] | Unset = UNSET
        if not isinstance(self.project_type, Unset):
            project_type = self.project_type.to_dict()

        projected_finish_date: None | str | Unset
        if isinstance(self.projected_finish_date, Unset):
            projected_finish_date = UNSET
        elif isinstance(self.projected_finish_date, datetime.date):
            projected_finish_date = self.projected_finish_date.isoformat()
        else:
            projected_finish_date = self.projected_finish_date

        sector: None | str | Unset
        if isinstance(self.sector, Unset):
            sector = UNSET
        elif (
            isinstance(self.sector, ListProjectsResponse200ItemSectorType1)
            or isinstance(self.sector, ListProjectsResponse200ItemSectorType2Type1)
            or isinstance(self.sector, ListProjectsResponse200ItemSectorType3Type1)
        ):
            sector = self.sector.value
        else:
            sector = self.sector

        square_feet: int | None | Unset
        if isinstance(self.square_feet, Unset):
            square_feet = UNSET
        else:
            square_feet = self.square_feet

        start_date: str | Unset = UNSET
        if not isinstance(self.start_date, Unset):
            start_date = self.start_date.isoformat()

        state_code = self.state_code

        store_number = self.store_number

        time_zone = self.time_zone

        total_value = self.total_value

        updated_at: str | Unset = UNSET
        if not isinstance(self.updated_at, Unset):
            updated_at = self.updated_at.isoformat()

        work_scope: None | str | Unset
        if isinstance(self.work_scope, Unset):
            work_scope = UNSET
        elif (
            isinstance(self.work_scope, ListProjectsResponse200ItemWorkScopeType1)
            or isinstance(
                self.work_scope, ListProjectsResponse200ItemWorkScopeType2Type1
            )
            or isinstance(
                self.work_scope, ListProjectsResponse200ItemWorkScopeType3Type1
            )
        ):
            work_scope = self.work_scope.value
        else:
            work_scope = self.work_scope

        zip_ = self.zip_

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if accounting_project_number is not UNSET:
            field_dict["accounting_project_number"] = accounting_project_number
        if active is not UNSET:
            field_dict["active"] = active
        if actual_start_date is not UNSET:
            field_dict["actual_start_date"] = actual_start_date
        if address is not UNSET:
            field_dict["address"] = address
        if city is not UNSET:
            field_dict["city"] = city
        if code is not UNSET:
            field_dict["code"] = code
        if company is not UNSET:
            field_dict["company"] = company
        if completion_date is not UNSET:
            field_dict["completion_date"] = completion_date
        if country_code is not UNSET:
            field_dict["country_code"] = country_code
        if county is not UNSET:
            field_dict["county"] = county
        if created_at is not UNSET:
            field_dict["created_at"] = created_at
        if created_by is not UNSET:
            field_dict["created_by"] = created_by
        if custom_fields is not UNSET:
            field_dict["custom_fields"] = custom_fields
        if delivery_method is not UNSET:
            field_dict["delivery_method"] = delivery_method
        if description is not UNSET:
            field_dict["description"] = description
        if designated_market_area is not UNSET:
            field_dict["designated_market_area"] = designated_market_area
        if display_name is not UNSET:
            field_dict["display_name"] = display_name
        if erp_integrated is not UNSET:
            field_dict["erp_integrated"] = erp_integrated
        if estimated_budget is not UNSET:
            field_dict["estimated_budget"] = estimated_budget
        if estimated_value is not UNSET:
            field_dict["estimated_value"] = estimated_value
        if fax is not UNSET:
            field_dict["fax"] = fax
        if id is not UNSET:
            field_dict["id"] = id
        if is_demo is not UNSET:
            field_dict["is_demo"] = is_demo
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude
        if name is not UNSET:
            field_dict["name"] = name
        if origin_code is not UNSET:
            field_dict["origin_code"] = origin_code
        if origin_data is not UNSET:
            field_dict["origin_data"] = origin_data
        if origin_id is not UNSET:
            field_dict["origin_id"] = origin_id
        if owners_project_id is not UNSET:
            field_dict["owners_project_id"] = owners_project_id
        if parent_job_id is not UNSET:
            field_dict["parent_job_id"] = parent_job_id
        if phone is not UNSET:
            field_dict["phone"] = phone
        if photo_id is not UNSET:
            field_dict["photo_id"] = photo_id
        if portfolio_program_uuid is not UNSET:
            field_dict["portfolio_program_uuid"] = portfolio_program_uuid
        if priority is not UNSET:
            field_dict["priority"] = priority
        if project_bid_type_id is not UNSET:
            field_dict["project_bid_type_id"] = project_bid_type_id
        if project_number is not UNSET:
            field_dict["project_number"] = project_number
        if project_owner_type_id is not UNSET:
            field_dict["project_owner_type_id"] = project_owner_type_id
        if project_region_id is not UNSET:
            field_dict["project_region_id"] = project_region_id
        if project_sector_id is not UNSET:
            field_dict["project_sector_id"] = project_sector_id
        if project_stage is not UNSET:
            field_dict["project_stage"] = project_stage
        if project_template is not UNSET:
            field_dict["project_template"] = project_template
        if project_type is not UNSET:
            field_dict["project_type"] = project_type
        if projected_finish_date is not UNSET:
            field_dict["projected_finish_date"] = projected_finish_date
        if sector is not UNSET:
            field_dict["sector"] = sector
        if square_feet is not UNSET:
            field_dict["square_feet"] = square_feet
        if start_date is not UNSET:
            field_dict["start_date"] = start_date
        if state_code is not UNSET:
            field_dict["state_code"] = state_code
        if store_number is not UNSET:
            field_dict["store_number"] = store_number
        if time_zone is not UNSET:
            field_dict["time_zone"] = time_zone
        if total_value is not UNSET:
            field_dict["total_value"] = total_value
        if updated_at is not UNSET:
            field_dict["updated_at"] = updated_at
        if work_scope is not UNSET:
            field_dict["work_scope"] = work_scope
        if zip_ is not UNSET:
            field_dict["zip"] = zip_

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.list_projects_response_200_item_company import (
            ListProjectsResponse200ItemCompany,
        )
        from ..models.list_projects_response_200_item_created_by_type_0 import (
            ListProjectsResponse200ItemCreatedByType0,
        )
        from ..models.list_projects_response_200_item_custom_fields import (
            ListProjectsResponse200ItemCustomFields,
        )
        from ..models.list_projects_response_200_item_project_stage import (
            ListProjectsResponse200ItemProjectStage,
        )
        from ..models.list_projects_response_200_item_project_template import (
            ListProjectsResponse200ItemProjectTemplate,
        )
        from ..models.list_projects_response_200_item_project_type import (
            ListProjectsResponse200ItemProjectType,
        )

        d = dict(src_dict)
        accounting_project_number = d.pop("accounting_project_number", UNSET)

        active = d.pop("active", UNSET)

        _actual_start_date = d.pop("actual_start_date", UNSET)
        actual_start_date: datetime.date | Unset
        if isinstance(_actual_start_date, Unset):
            actual_start_date = UNSET
        else:
            actual_start_date = datetime.date.fromisoformat(_actual_start_date)

        address = d.pop("address", UNSET)

        city = d.pop("city", UNSET)

        def _parse_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        code = _parse_code(d.pop("code", UNSET))

        _company = d.pop("company", UNSET)
        company: ListProjectsResponse200ItemCompany | Unset
        if isinstance(_company, Unset):
            company = UNSET
        else:
            company = ListProjectsResponse200ItemCompany.from_dict(_company)

        _completion_date = d.pop("completion_date", UNSET)
        completion_date: datetime.date | Unset
        if isinstance(_completion_date, Unset):
            completion_date = UNSET
        else:
            completion_date = datetime.date.fromisoformat(_completion_date)

        country_code = d.pop("country_code", UNSET)

        county = d.pop("county", UNSET)

        _created_at = d.pop("created_at", UNSET)
        created_at: datetime.datetime | Unset
        if isinstance(_created_at, Unset):
            created_at = UNSET
        else:
            created_at = datetime.datetime.fromisoformat(_created_at)

        def _parse_created_by(
            data: object,
        ) -> ListProjectsResponse200ItemCreatedByType0 | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, dict):
                    raise TypeError()
                created_by_type_0 = ListProjectsResponse200ItemCreatedByType0.from_dict(
                    data
                )

                return created_by_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(ListProjectsResponse200ItemCreatedByType0 | None | Unset, data)

        created_by = _parse_created_by(d.pop("created_by", UNSET))

        _custom_fields = d.pop("custom_fields", UNSET)
        custom_fields: ListProjectsResponse200ItemCustomFields | Unset
        if isinstance(_custom_fields, Unset):
            custom_fields = UNSET
        else:
            custom_fields = ListProjectsResponse200ItemCustomFields.from_dict(
                _custom_fields
            )

        def _parse_delivery_method(
            data: object,
        ) -> (
            ListProjectsResponse200ItemDeliveryMethodType1
            | ListProjectsResponse200ItemDeliveryMethodType2Type1
            | ListProjectsResponse200ItemDeliveryMethodType3Type1
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                delivery_method_type_1 = ListProjectsResponse200ItemDeliveryMethodType1(
                    data
                )

                return delivery_method_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                delivery_method_type_2_type_1 = (
                    ListProjectsResponse200ItemDeliveryMethodType2Type1(data)
                )

                return delivery_method_type_2_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                delivery_method_type_3_type_1 = (
                    ListProjectsResponse200ItemDeliveryMethodType3Type1(data)
                )

                return delivery_method_type_3_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListProjectsResponse200ItemDeliveryMethodType1
                | ListProjectsResponse200ItemDeliveryMethodType2Type1
                | ListProjectsResponse200ItemDeliveryMethodType3Type1
                | None
                | Unset,
                data,
            )

        delivery_method = _parse_delivery_method(d.pop("delivery_method", UNSET))

        def _parse_description(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        description = _parse_description(d.pop("description", UNSET))

        designated_market_area = d.pop("designated_market_area", UNSET)

        display_name = d.pop("display_name", UNSET)

        erp_integrated = d.pop("erp_integrated", UNSET)

        def _parse_estimated_budget(data: object) -> float | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(float | None | Unset, data)

        estimated_budget = _parse_estimated_budget(d.pop("estimated_budget", UNSET))

        estimated_value = d.pop("estimated_value", UNSET)

        def _parse_fax(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        fax = _parse_fax(d.pop("fax", UNSET))

        id = d.pop("id", UNSET)

        is_demo = d.pop("is_demo", UNSET)

        latitude = d.pop("latitude", UNSET)

        longitude = d.pop("longitude", UNSET)

        name = d.pop("name", UNSET)

        def _parse_origin_code(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_code = _parse_origin_code(d.pop("origin_code", UNSET))

        def _parse_origin_data(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_data = _parse_origin_data(d.pop("origin_data", UNSET))

        def _parse_origin_id(data: object) -> None | str | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(None | str | Unset, data)

        origin_id = _parse_origin_id(d.pop("origin_id", UNSET))

        def _parse_owners_project_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        owners_project_id = _parse_owners_project_id(d.pop("owners_project_id", UNSET))

        def _parse_parent_job_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        parent_job_id = _parse_parent_job_id(d.pop("parent_job_id", UNSET))

        phone = d.pop("phone", UNSET)

        def _parse_photo_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        photo_id = _parse_photo_id(d.pop("photo_id", UNSET))

        def _parse_portfolio_program_uuid(data: object) -> None | Unset | UUID:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                portfolio_program_uuid_type_0 = UUID(data)

                return portfolio_program_uuid_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(None | Unset | UUID, data)

        portfolio_program_uuid = _parse_portfolio_program_uuid(
            d.pop("portfolio_program_uuid", UNSET)
        )

        _priority = d.pop("priority", UNSET)
        priority: ListProjectsResponse200ItemPriority | Unset
        if isinstance(_priority, Unset):
            priority = UNSET
        else:
            priority = ListProjectsResponse200ItemPriority(_priority)

        def _parse_project_bid_type_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        project_bid_type_id = _parse_project_bid_type_id(
            d.pop("project_bid_type_id", UNSET)
        )

        project_number = d.pop("project_number", UNSET)

        def _parse_project_owner_type_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        project_owner_type_id = _parse_project_owner_type_id(
            d.pop("project_owner_type_id", UNSET)
        )

        def _parse_project_region_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        project_region_id = _parse_project_region_id(d.pop("project_region_id", UNSET))

        def _parse_project_sector_id(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        project_sector_id = _parse_project_sector_id(d.pop("project_sector_id", UNSET))

        _project_stage = d.pop("project_stage", UNSET)
        project_stage: ListProjectsResponse200ItemProjectStage | Unset
        if isinstance(_project_stage, Unset):
            project_stage = UNSET
        else:
            project_stage = ListProjectsResponse200ItemProjectStage.from_dict(
                _project_stage
            )

        _project_template = d.pop("project_template", UNSET)
        project_template: ListProjectsResponse200ItemProjectTemplate | Unset
        if isinstance(_project_template, Unset):
            project_template = UNSET
        else:
            project_template = ListProjectsResponse200ItemProjectTemplate.from_dict(
                _project_template
            )

        _project_type = d.pop("project_type", UNSET)
        project_type: ListProjectsResponse200ItemProjectType | Unset
        if isinstance(_project_type, Unset):
            project_type = UNSET
        else:
            project_type = ListProjectsResponse200ItemProjectType.from_dict(
                _project_type
            )

        def _parse_projected_finish_date(data: object) -> datetime.date | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                projected_finish_date_type_0 = datetime.date.fromisoformat(data)

                return projected_finish_date_type_0
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(datetime.date | None | Unset, data)

        projected_finish_date = _parse_projected_finish_date(
            d.pop("projected_finish_date", UNSET)
        )

        def _parse_sector(
            data: object,
        ) -> (
            ListProjectsResponse200ItemSectorType1
            | ListProjectsResponse200ItemSectorType2Type1
            | ListProjectsResponse200ItemSectorType3Type1
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                sector_type_1 = ListProjectsResponse200ItemSectorType1(data)

                return sector_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                sector_type_2_type_1 = ListProjectsResponse200ItemSectorType2Type1(data)

                return sector_type_2_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                sector_type_3_type_1 = ListProjectsResponse200ItemSectorType3Type1(data)

                return sector_type_3_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListProjectsResponse200ItemSectorType1
                | ListProjectsResponse200ItemSectorType2Type1
                | ListProjectsResponse200ItemSectorType3Type1
                | None
                | Unset,
                data,
            )

        sector = _parse_sector(d.pop("sector", UNSET))

        def _parse_square_feet(data: object) -> int | None | Unset:
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            return cast(int | None | Unset, data)

        square_feet = _parse_square_feet(d.pop("square_feet", UNSET))

        _start_date = d.pop("start_date", UNSET)
        start_date: datetime.date | Unset
        if isinstance(_start_date, Unset):
            start_date = UNSET
        else:
            start_date = datetime.date.fromisoformat(_start_date)

        state_code = d.pop("state_code", UNSET)

        store_number = d.pop("store_number", UNSET)

        time_zone = d.pop("time_zone", UNSET)

        total_value = d.pop("total_value", UNSET)

        _updated_at = d.pop("updated_at", UNSET)
        updated_at: datetime.datetime | Unset
        if isinstance(_updated_at, Unset):
            updated_at = UNSET
        else:
            updated_at = datetime.datetime.fromisoformat(_updated_at)

        def _parse_work_scope(
            data: object,
        ) -> (
            ListProjectsResponse200ItemWorkScopeType1
            | ListProjectsResponse200ItemWorkScopeType2Type1
            | ListProjectsResponse200ItemWorkScopeType3Type1
            | None
            | Unset
        ):
            if data is None:
                return data
            if isinstance(data, Unset):
                return data
            try:
                if not isinstance(data, str):
                    raise TypeError()
                work_scope_type_1 = ListProjectsResponse200ItemWorkScopeType1(data)

                return work_scope_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                work_scope_type_2_type_1 = (
                    ListProjectsResponse200ItemWorkScopeType2Type1(data)
                )

                return work_scope_type_2_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            try:
                if not isinstance(data, str):
                    raise TypeError()
                work_scope_type_3_type_1 = (
                    ListProjectsResponse200ItemWorkScopeType3Type1(data)
                )

                return work_scope_type_3_type_1
            except (TypeError, ValueError, AttributeError, KeyError):
                pass
            return cast(
                ListProjectsResponse200ItemWorkScopeType1
                | ListProjectsResponse200ItemWorkScopeType2Type1
                | ListProjectsResponse200ItemWorkScopeType3Type1
                | None
                | Unset,
                data,
            )

        work_scope = _parse_work_scope(d.pop("work_scope", UNSET))

        zip_ = d.pop("zip", UNSET)

        list_projects_response_200_item = cls(
            accounting_project_number=accounting_project_number,
            active=active,
            actual_start_date=actual_start_date,
            address=address,
            city=city,
            code=code,
            company=company,
            completion_date=completion_date,
            country_code=country_code,
            county=county,
            created_at=created_at,
            created_by=created_by,
            custom_fields=custom_fields,
            delivery_method=delivery_method,
            description=description,
            designated_market_area=designated_market_area,
            display_name=display_name,
            erp_integrated=erp_integrated,
            estimated_budget=estimated_budget,
            estimated_value=estimated_value,
            fax=fax,
            id=id,
            is_demo=is_demo,
            latitude=latitude,
            longitude=longitude,
            name=name,
            origin_code=origin_code,
            origin_data=origin_data,
            origin_id=origin_id,
            owners_project_id=owners_project_id,
            parent_job_id=parent_job_id,
            phone=phone,
            photo_id=photo_id,
            portfolio_program_uuid=portfolio_program_uuid,
            priority=priority,
            project_bid_type_id=project_bid_type_id,
            project_number=project_number,
            project_owner_type_id=project_owner_type_id,
            project_region_id=project_region_id,
            project_sector_id=project_sector_id,
            project_stage=project_stage,
            project_template=project_template,
            project_type=project_type,
            projected_finish_date=projected_finish_date,
            sector=sector,
            square_feet=square_feet,
            start_date=start_date,
            state_code=state_code,
            store_number=store_number,
            time_zone=time_zone,
            total_value=total_value,
            updated_at=updated_at,
            work_scope=work_scope,
            zip_=zip_,
        )

        list_projects_response_200_item.additional_properties = d
        return list_projects_response_200_item

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
