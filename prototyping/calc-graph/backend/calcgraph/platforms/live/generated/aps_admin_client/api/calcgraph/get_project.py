from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.fields import Fields
from ...models.project import Project
from ...models.region import Region
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: str,
    *,
    fields: list[Fields] | Unset = UNSET,
    accept_language: str | Unset = UNSET,
    region: Region | Unset = UNSET,
    user_id: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(accept_language, Unset):
        headers["Accept-Language"] = accept_language

    if not isinstance(region, Unset):
        headers["Region"] = str(region)

    if not isinstance(user_id, Unset):
        headers["User-Id"] = user_id

    params: dict[str, Any] = {}

    json_fields: list[str] | Unset = UNSET
    if not isinstance(fields, Unset):
        json_fields = []
        for componentsschemasfields_internal_item_data in fields:
            componentsschemasfields_internal_item = (
                componentsschemasfields_internal_item_data.value
            )
            json_fields.append(componentsschemasfields_internal_item)

    params["fields"] = json_fields

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/construction/admin/v1/projects/{project_id}".format(
            project_id=quote(str(project_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Project | None:
    if response.status_code == 200:
        response_200 = Project.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Project]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    project_id: str,
    *,
    client: AuthenticatedClient,
    fields: list[Fields] | Unset = UNSET,
    accept_language: str | Unset = UNSET,
    region: Region | Unset = UNSET,
    user_id: str | Unset = UNSET,
) -> Response[Project]:
    """Get a project by ID

     Retrieves a project specified by project ID.

    Args:
        project_id (str):
        fields (list[Fields] | Unset):
        accept_language (str | Unset):
        region (Region | Unset): Specifies the region where your request should be routed.
            Possible values are:
            - ``US`` - Data center for the US region.
            - ``EMEA`` - Data center for the European Union, Middle East, and Africa regions.
            - ``AUS`` - Data center for the Australia region.
            - ``CAN`` - Data center for the Canada region.
            - ``DEU`` - Data center for the Germany region.
            - ``IND`` - Data center for the India region.
            - ``JPN`` - Data center for the Japan region.
            - ``GBR`` - Data center for the United Kingdom region.
        user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Project]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        fields=fields,
        accept_language=accept_language,
        region=region,
        user_id=user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    project_id: str,
    *,
    client: AuthenticatedClient,
    fields: list[Fields] | Unset = UNSET,
    accept_language: str | Unset = UNSET,
    region: Region | Unset = UNSET,
    user_id: str | Unset = UNSET,
) -> Project | None:
    """Get a project by ID

     Retrieves a project specified by project ID.

    Args:
        project_id (str):
        fields (list[Fields] | Unset):
        accept_language (str | Unset):
        region (Region | Unset): Specifies the region where your request should be routed.
            Possible values are:
            - ``US`` - Data center for the US region.
            - ``EMEA`` - Data center for the European Union, Middle East, and Africa regions.
            - ``AUS`` - Data center for the Australia region.
            - ``CAN`` - Data center for the Canada region.
            - ``DEU`` - Data center for the Germany region.
            - ``IND`` - Data center for the India region.
            - ``JPN`` - Data center for the Japan region.
            - ``GBR`` - Data center for the United Kingdom region.
        user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Project
    """

    return sync_detailed(
        project_id=project_id,
        client=client,
        fields=fields,
        accept_language=accept_language,
        region=region,
        user_id=user_id,
    ).parsed


async def asyncio_detailed(
    project_id: str,
    *,
    client: AuthenticatedClient,
    fields: list[Fields] | Unset = UNSET,
    accept_language: str | Unset = UNSET,
    region: Region | Unset = UNSET,
    user_id: str | Unset = UNSET,
) -> Response[Project]:
    """Get a project by ID

     Retrieves a project specified by project ID.

    Args:
        project_id (str):
        fields (list[Fields] | Unset):
        accept_language (str | Unset):
        region (Region | Unset): Specifies the region where your request should be routed.
            Possible values are:
            - ``US`` - Data center for the US region.
            - ``EMEA`` - Data center for the European Union, Middle East, and Africa regions.
            - ``AUS`` - Data center for the Australia region.
            - ``CAN`` - Data center for the Canada region.
            - ``DEU`` - Data center for the Germany region.
            - ``IND`` - Data center for the India region.
            - ``JPN`` - Data center for the Japan region.
            - ``GBR`` - Data center for the United Kingdom region.
        user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Project]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        fields=fields,
        accept_language=accept_language,
        region=region,
        user_id=user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: str,
    *,
    client: AuthenticatedClient,
    fields: list[Fields] | Unset = UNSET,
    accept_language: str | Unset = UNSET,
    region: Region | Unset = UNSET,
    user_id: str | Unset = UNSET,
) -> Project | None:
    """Get a project by ID

     Retrieves a project specified by project ID.

    Args:
        project_id (str):
        fields (list[Fields] | Unset):
        accept_language (str | Unset):
        region (Region | Unset): Specifies the region where your request should be routed.
            Possible values are:
            - ``US`` - Data center for the US region.
            - ``EMEA`` - Data center for the European Union, Middle East, and Africa regions.
            - ``AUS`` - Data center for the Australia region.
            - ``CAN`` - Data center for the Canada region.
            - ``DEU`` - Data center for the Germany region.
            - ``IND`` - Data center for the India region.
            - ``JPN`` - Data center for the Japan region.
            - ``GBR`` - Data center for the United Kingdom region.
        user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Project
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            client=client,
            fields=fields,
            accept_language=accept_language,
            region=region,
            user_id=user_id,
        )
    ).parsed
