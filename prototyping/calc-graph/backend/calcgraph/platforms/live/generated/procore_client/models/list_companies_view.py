from enum import StrEnum


class ListCompaniesView(StrEnum):
    ALL_ZONES_WITH_IS_DEMO = "all_zones_with_is_demo"
    COMPACT = "compact"
    ENABLE_DOCUSIGN_INTEGRATION = "enable_docusign_integration"
    ERP = "erp"
    LEGACY_INTERNAL_SUPER_USER_VIEW = "legacy_internal_super_user_view"
    MY_COMPANY = "my_company"
    PCN = "pcn"
    SHOW = "show"
    WITH_LOCALE_AND_SEGMENT = "with_locale_and_segment"
    WITH_OWNERS = "with_owners"
    WITH_OWNERS_AND_TIMED_OUT = "with_owners_and_timed_out"
    WITH_ROOT = "with_root"

    def __str__(self) -> str:
        return str(self.value)
