"""Contains all the data models used in inputs/outputs"""

from .base_attributes_extension_object_with_schema_link import (
    BaseAttributesExtensionObjectWithSchemaLink,
)
from .base_attributes_extension_object_with_schema_link_data import (
    BaseAttributesExtensionObjectWithSchemaLinkData,
)
from .base_attributes_extension_object_with_schema_link_schema import (
    BaseAttributesExtensionObjectWithSchemaLinkSchema,
)
from .hub_data import HubData
from .hub_data_attributes import HubDataAttributes
from .hub_data_relationships import HubDataRelationships
from .hub_data_relationships_pim_collection import HubDataRelationshipsPimCollection
from .hub_data_relationships_projects import HubDataRelationshipsProjects
from .hubs_response import HubsResponse
from .json_api_link import JsonApiLink
from .json_api_links_related import JsonApiLinksRelated
from .json_api_links_related_related import JsonApiLinksRelatedRelated
from .json_api_links_self import JsonApiLinksSelf
from .json_api_links_self_and_web_view import JsonApiLinksSelfAndWebView
from .json_api_links_self_self import JsonApiLinksSelfSelf
from .json_api_meta_link import JsonApiMetaLink
from .json_api_relationships_links_internal_resource import (
    JsonApiRelationshipsLinksInternalResource,
)
from .json_api_relationships_links_only_bim import JsonApiRelationshipsLinksOnlyBim
from .json_api_relationships_links_root_folder import (
    JsonApiRelationshipsLinksRootFolder,
)
from .json_api_type_id import JsonApiTypeId
from .json_api_version import JsonApiVersion
from .json_api_version_value import JsonApiVersionValue
from .pagination_info import PaginationInfo
from .pagination_info_first import PaginationInfoFirst
from .pagination_info_next import PaginationInfoNext
from .pagination_info_prev import PaginationInfoPrev
from .pagination_info_self import PaginationInfoSelf
from .project import Project
from .project_data import ProjectData
from .project_data_attributes import ProjectDataAttributes
from .project_data_relationships import ProjectDataRelationships
from .project_data_relationships_top_folders import ProjectDataRelationshipsTopFolders
from .project_extension_with_schema_link import ProjectExtensionWithSchemaLink
from .project_extension_with_schema_link_data import ProjectExtensionWithSchemaLinkData
from .project_type_bim_360_acc import ProjectTypeBim360Acc
from .projects_response import ProjectsResponse
from .region import Region
from .type_hub import TypeHub
from .type_project import TypeProject
from .web_view_link import WebViewLink

__all__ = (
    "BaseAttributesExtensionObjectWithSchemaLink",
    "BaseAttributesExtensionObjectWithSchemaLinkData",
    "BaseAttributesExtensionObjectWithSchemaLinkSchema",
    "HubData",
    "HubDataAttributes",
    "HubDataRelationships",
    "HubDataRelationshipsPimCollection",
    "HubDataRelationshipsProjects",
    "HubsResponse",
    "JsonApiLink",
    "JsonApiLinksRelated",
    "JsonApiLinksRelatedRelated",
    "JsonApiLinksSelf",
    "JsonApiLinksSelfAndWebView",
    "JsonApiLinksSelfSelf",
    "JsonApiMetaLink",
    "JsonApiRelationshipsLinksInternalResource",
    "JsonApiRelationshipsLinksOnlyBim",
    "JsonApiRelationshipsLinksRootFolder",
    "JsonApiTypeId",
    "JsonApiVersion",
    "JsonApiVersionValue",
    "PaginationInfo",
    "PaginationInfoFirst",
    "PaginationInfoNext",
    "PaginationInfoPrev",
    "PaginationInfoSelf",
    "Project",
    "ProjectData",
    "ProjectDataAttributes",
    "ProjectDataRelationships",
    "ProjectDataRelationshipsTopFolders",
    "ProjectExtensionWithSchemaLink",
    "ProjectExtensionWithSchemaLinkData",
    "ProjectTypeBim360Acc",
    "ProjectsResponse",
    "Region",
    "TypeHub",
    "TypeProject",
    "WebViewLink",
)
