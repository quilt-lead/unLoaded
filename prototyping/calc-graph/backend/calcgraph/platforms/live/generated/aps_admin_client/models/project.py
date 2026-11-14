from __future__ import annotations

from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Self, TypeVar

from attrs import define as _attrs_define
from attrs import field as _attrs_field

from ..types import UNSET, Unset

if TYPE_CHECKING:
    from ..models.project_products_item import ProjectProductsItem
    from ..models.project_project_value import ProjectProjectValue


T = TypeVar("T", bound="Project")


@_attrs_define
class Project:
    """
    Attributes:
        account_id (str | Unset): The ID of the account the project is associated with.
        address_line_1 (str | Unset): Address line 1 for the project.
            Max length: 255
        address_line_2 (str | Unset): Address line 2 for the project.
            Max length: 255
        admin_group_id (str | Unset): Not relevant
        business_unit_id (str | Unset): The ID of the business unit that the project is associated with.
        city (str | Unset): The city in which the project is located.
        classification (str | Unset): The project’s purpose. Possible values: production, template, component, sample
        company_count (int | Unset): The total number of companies associated with the project.
        construction_type (str | Unset): The construction type of the project. Following is a list of recommended
            values; however, any value is accepted.
        contract_type (str | Unset): The contract type of the project. Following is a list of recommended values;
            however, any value is accepted.
        country (str | Unset): The country in which the project is located. Only valid country names and ISO 3166-1
            alpha-2 codes is accepted.
        created_at (str | Unset): The timestamp when the project was created, in ISO 8601 format.
        current_phase (str | Unset): The current phase of the project. Following is a list of recommended values;
            however, any value is accepted.
        delivery_method (str | Unset): The delivery method of the project. Following is a list of recommended values;
            however, any value is accepted.
        end_date (str | Unset): The estimated end date for the project, in ISO 8601 format.
        id (str | Unset): The internally generated ID for the project.
        image_url (str | Unset): The URL of the project image.
        job_number (str | Unset): A job identifier that’s defined for the project by the user. This ID was defined when
            the project was created.
            Max length: 100
        last_sign_in (str | Unset): The timestamp of the last time someone signed into the project.
        latitude (str | Unset): The latitude of the location of the project.
        longitude (str | Unset): The longitude of the location of the project.
        member_count (int | Unset): The total number of members on the project.
        member_group_id (str | Unset): Not relevant
        name (str | Unset): The name of the project.
            Max length: 255
        platform (str | Unset): The APS platform that the project belongs to.
        postal_code (str | Unset): The zip or postal code in which the project is located.
        products (list[ProjectProductsItem] | Unset): An array of the product objects associated with the project.
        project_value (ProjectProjectValue | Unset): The value of the project. When updating the project value, both the
            value and currency parameters are required.
        sheet_count (int | Unset): The total number of sheets associated with the project.
        start_date (str | Unset): The estimated start date for the project, in ISO 8601 format.
        state_or_province (str | Unset): The state or province in which the project is located. Only valid
            state/province names and ISO 3166-1 alpha-2 codes is accepted. The provided state or province must exist in the
            country of the project.
        status (str | Unset): The status of the project.
        template_id (str | Unset): The ID of the project that was used as a template to create this project.
        thumbnail_image_url (str | Unset): The URL of the project thumbnail image.
        timezone (str | Unset): The time zone in which the project is located. Note that this field can be NULL.
        type_ (str | Unset): The type of the project.
        updated_at (str | Unset): The timestamp when the project was last updated, in ISO 8601 format. This reflects
            only changes to the project fields and not changes to any resources in the project.
    """

    account_id: str | Unset = UNSET
    address_line_1: str | Unset = UNSET
    address_line_2: str | Unset = UNSET
    admin_group_id: str | Unset = UNSET
    business_unit_id: str | Unset = UNSET
    city: str | Unset = UNSET
    classification: str | Unset = UNSET
    company_count: int | Unset = UNSET
    construction_type: str | Unset = UNSET
    contract_type: str | Unset = UNSET
    country: str | Unset = UNSET
    created_at: str | Unset = UNSET
    current_phase: str | Unset = UNSET
    delivery_method: str | Unset = UNSET
    end_date: str | Unset = UNSET
    id: str | Unset = UNSET
    image_url: str | Unset = UNSET
    job_number: str | Unset = UNSET
    last_sign_in: str | Unset = UNSET
    latitude: str | Unset = UNSET
    longitude: str | Unset = UNSET
    member_count: int | Unset = UNSET
    member_group_id: str | Unset = UNSET
    name: str | Unset = UNSET
    platform: str | Unset = UNSET
    postal_code: str | Unset = UNSET
    products: list[ProjectProductsItem] | Unset = UNSET
    project_value: ProjectProjectValue | Unset = UNSET
    sheet_count: int | Unset = UNSET
    start_date: str | Unset = UNSET
    state_or_province: str | Unset = UNSET
    status: str | Unset = UNSET
    template_id: str | Unset = UNSET
    thumbnail_image_url: str | Unset = UNSET
    timezone: str | Unset = UNSET
    type_: str | Unset = UNSET
    updated_at: str | Unset = UNSET
    additional_properties: dict[str, Any] = _attrs_field(init=False, factory=dict)

    def to_dict(self) -> dict[str, Any]:
        account_id = self.account_id

        address_line_1 = self.address_line_1

        address_line_2 = self.address_line_2

        admin_group_id = self.admin_group_id

        business_unit_id = self.business_unit_id

        city = self.city

        classification = self.classification

        company_count = self.company_count

        construction_type = self.construction_type

        contract_type = self.contract_type

        country = self.country

        created_at = self.created_at

        current_phase = self.current_phase

        delivery_method = self.delivery_method

        end_date = self.end_date

        id = self.id

        image_url = self.image_url

        job_number = self.job_number

        last_sign_in = self.last_sign_in

        latitude = self.latitude

        longitude = self.longitude

        member_count = self.member_count

        member_group_id = self.member_group_id

        name = self.name

        platform = self.platform

        postal_code = self.postal_code

        products: list[dict[str, Any]] | Unset = UNSET
        if not isinstance(self.products, Unset):
            products = []
            for products_item_data in self.products:
                products_item = products_item_data.to_dict()
                products.append(products_item)

        project_value: dict[str, Any] | Unset = UNSET
        if not isinstance(self.project_value, Unset):
            project_value = self.project_value.to_dict()

        sheet_count = self.sheet_count

        start_date = self.start_date

        state_or_province = self.state_or_province

        status = self.status

        template_id = self.template_id

        thumbnail_image_url = self.thumbnail_image_url

        timezone = self.timezone

        type_ = self.type_

        updated_at = self.updated_at

        field_dict: dict[str, Any] = {}
        field_dict.update(self.additional_properties)
        field_dict.update({})
        if account_id is not UNSET:
            field_dict["accountId"] = account_id
        if address_line_1 is not UNSET:
            field_dict["addressLine1"] = address_line_1
        if address_line_2 is not UNSET:
            field_dict["addressLine2"] = address_line_2
        if admin_group_id is not UNSET:
            field_dict["adminGroupId"] = admin_group_id
        if business_unit_id is not UNSET:
            field_dict["businessUnitId"] = business_unit_id
        if city is not UNSET:
            field_dict["city"] = city
        if classification is not UNSET:
            field_dict["classification"] = classification
        if company_count is not UNSET:
            field_dict["companyCount"] = company_count
        if construction_type is not UNSET:
            field_dict["constructionType"] = construction_type
        if contract_type is not UNSET:
            field_dict["contractType"] = contract_type
        if country is not UNSET:
            field_dict["country"] = country
        if created_at is not UNSET:
            field_dict["createdAt"] = created_at
        if current_phase is not UNSET:
            field_dict["currentPhase"] = current_phase
        if delivery_method is not UNSET:
            field_dict["deliveryMethod"] = delivery_method
        if end_date is not UNSET:
            field_dict["endDate"] = end_date
        if id is not UNSET:
            field_dict["id"] = id
        if image_url is not UNSET:
            field_dict["imageUrl"] = image_url
        if job_number is not UNSET:
            field_dict["jobNumber"] = job_number
        if last_sign_in is not UNSET:
            field_dict["lastSignIn"] = last_sign_in
        if latitude is not UNSET:
            field_dict["latitude"] = latitude
        if longitude is not UNSET:
            field_dict["longitude"] = longitude
        if member_count is not UNSET:
            field_dict["memberCount"] = member_count
        if member_group_id is not UNSET:
            field_dict["memberGroupId"] = member_group_id
        if name is not UNSET:
            field_dict["name"] = name
        if platform is not UNSET:
            field_dict["platform"] = platform
        if postal_code is not UNSET:
            field_dict["postalCode"] = postal_code
        if products is not UNSET:
            field_dict["products"] = products
        if project_value is not UNSET:
            field_dict["projectValue"] = project_value
        if sheet_count is not UNSET:
            field_dict["sheetCount"] = sheet_count
        if start_date is not UNSET:
            field_dict["startDate"] = start_date
        if state_or_province is not UNSET:
            field_dict["stateOrProvince"] = state_or_province
        if status is not UNSET:
            field_dict["status"] = status
        if template_id is not UNSET:
            field_dict["templateId"] = template_id
        if thumbnail_image_url is not UNSET:
            field_dict["thumbnailImageUrl"] = thumbnail_image_url
        if timezone is not UNSET:
            field_dict["timezone"] = timezone
        if type_ is not UNSET:
            field_dict["type"] = type_
        if updated_at is not UNSET:
            field_dict["updatedAt"] = updated_at

        return field_dict

    @classmethod
    def from_dict(cls, src_dict: Mapping[str, Any]) -> Self:
        from ..models.project_products_item import ProjectProductsItem
        from ..models.project_project_value import ProjectProjectValue

        d = dict(src_dict)
        account_id = d.pop("accountId", UNSET)

        address_line_1 = d.pop("addressLine1", UNSET)

        address_line_2 = d.pop("addressLine2", UNSET)

        admin_group_id = d.pop("adminGroupId", UNSET)

        business_unit_id = d.pop("businessUnitId", UNSET)

        city = d.pop("city", UNSET)

        classification = d.pop("classification", UNSET)

        company_count = d.pop("companyCount", UNSET)

        construction_type = d.pop("constructionType", UNSET)

        contract_type = d.pop("contractType", UNSET)

        country = d.pop("country", UNSET)

        created_at = d.pop("createdAt", UNSET)

        current_phase = d.pop("currentPhase", UNSET)

        delivery_method = d.pop("deliveryMethod", UNSET)

        end_date = d.pop("endDate", UNSET)

        id = d.pop("id", UNSET)

        image_url = d.pop("imageUrl", UNSET)

        job_number = d.pop("jobNumber", UNSET)

        last_sign_in = d.pop("lastSignIn", UNSET)

        latitude = d.pop("latitude", UNSET)

        longitude = d.pop("longitude", UNSET)

        member_count = d.pop("memberCount", UNSET)

        member_group_id = d.pop("memberGroupId", UNSET)

        name = d.pop("name", UNSET)

        platform = d.pop("platform", UNSET)

        postal_code = d.pop("postalCode", UNSET)

        _products = d.pop("products", UNSET)
        products: list[ProjectProductsItem] | Unset = UNSET
        if _products is not UNSET:
            products = []
            for products_item_data in _products:
                products_item = ProjectProductsItem.from_dict(products_item_data)

                products.append(products_item)

        _project_value = d.pop("projectValue", UNSET)
        project_value: ProjectProjectValue | Unset
        if isinstance(_project_value, Unset):
            project_value = UNSET
        else:
            project_value = ProjectProjectValue.from_dict(_project_value)

        sheet_count = d.pop("sheetCount", UNSET)

        start_date = d.pop("startDate", UNSET)

        state_or_province = d.pop("stateOrProvince", UNSET)

        status = d.pop("status", UNSET)

        template_id = d.pop("templateId", UNSET)

        thumbnail_image_url = d.pop("thumbnailImageUrl", UNSET)

        timezone = d.pop("timezone", UNSET)

        type_ = d.pop("type", UNSET)

        updated_at = d.pop("updatedAt", UNSET)

        project = cls(
            account_id=account_id,
            address_line_1=address_line_1,
            address_line_2=address_line_2,
            admin_group_id=admin_group_id,
            business_unit_id=business_unit_id,
            city=city,
            classification=classification,
            company_count=company_count,
            construction_type=construction_type,
            contract_type=contract_type,
            country=country,
            created_at=created_at,
            current_phase=current_phase,
            delivery_method=delivery_method,
            end_date=end_date,
            id=id,
            image_url=image_url,
            job_number=job_number,
            last_sign_in=last_sign_in,
            latitude=latitude,
            longitude=longitude,
            member_count=member_count,
            member_group_id=member_group_id,
            name=name,
            platform=platform,
            postal_code=postal_code,
            products=products,
            project_value=project_value,
            sheet_count=sheet_count,
            start_date=start_date,
            state_or_province=state_or_province,
            status=status,
            template_id=template_id,
            thumbnail_image_url=thumbnail_image_url,
            timezone=timezone,
            type_=type_,
            updated_at=updated_at,
        )

        project.additional_properties = d
        return project

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
