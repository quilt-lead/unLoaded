from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.region import Region
from ...models.types_page import TypesPage
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: str,
    *,
    include: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_ads_region, Unset):
        headers["x-ads-region"] = str(x_ads_region)

    params: dict[str, Any] = {}

    params["include"] = include

    params["limit"] = limit

    params["offset"] = offset

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/construction/issues/v1/projects/{project_id}/issue-types".format(
            project_id=quote(str(project_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> TypesPage | None:
    if response.status_code == 200:
        response_200 = TypesPage.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[TypesPage]:
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
    include: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> Response[TypesPage]:
    """Your GET endpoint

     Retrieves a project’s categories and types.

    Args:
        project_id (str):
        include (str | Unset):
        limit (int | Unset):
        offset (int | Unset):
        x_ads_region (Region | Unset): Specifies where the bucket containing the object is stored.
            Possible values are:
                        - ``US`` - (Default) Data center for the US region.
                        - ``EMEA`` - Data center for the European Union, Middle East, and Africa.
                        - ``AUS`` -  Data center for Australia.
                        - ``CAN`` - Data center for the Canada region.
                        - ``DEU`` - Data center for the Germany region.
                        - ``IND`` - Data center for the India region.
                        - ``JPN`` - Data center for the Japan region.
                        - ``GBR`` - Data center for the United Kingdom region.
            **Note:** Beta features are subject to change. Please do not use in production
            environments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[TypesPage]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        include=include,
        limit=limit,
        offset=offset,
        x_ads_region=x_ads_region,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    project_id: str,
    *,
    client: AuthenticatedClient,
    include: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> TypesPage | None:
    """Your GET endpoint

     Retrieves a project’s categories and types.

    Args:
        project_id (str):
        include (str | Unset):
        limit (int | Unset):
        offset (int | Unset):
        x_ads_region (Region | Unset): Specifies where the bucket containing the object is stored.
            Possible values are:
                        - ``US`` - (Default) Data center for the US region.
                        - ``EMEA`` - Data center for the European Union, Middle East, and Africa.
                        - ``AUS`` -  Data center for Australia.
                        - ``CAN`` - Data center for the Canada region.
                        - ``DEU`` - Data center for the Germany region.
                        - ``IND`` - Data center for the India region.
                        - ``JPN`` - Data center for the Japan region.
                        - ``GBR`` - Data center for the United Kingdom region.
            **Note:** Beta features are subject to change. Please do not use in production
            environments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        TypesPage
    """

    return sync_detailed(
        project_id=project_id,
        client=client,
        include=include,
        limit=limit,
        offset=offset,
        x_ads_region=x_ads_region,
    ).parsed


async def asyncio_detailed(
    project_id: str,
    *,
    client: AuthenticatedClient,
    include: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> Response[TypesPage]:
    """Your GET endpoint

     Retrieves a project’s categories and types.

    Args:
        project_id (str):
        include (str | Unset):
        limit (int | Unset):
        offset (int | Unset):
        x_ads_region (Region | Unset): Specifies where the bucket containing the object is stored.
            Possible values are:
                        - ``US`` - (Default) Data center for the US region.
                        - ``EMEA`` - Data center for the European Union, Middle East, and Africa.
                        - ``AUS`` -  Data center for Australia.
                        - ``CAN`` - Data center for the Canada region.
                        - ``DEU`` - Data center for the Germany region.
                        - ``IND`` - Data center for the India region.
                        - ``JPN`` - Data center for the Japan region.
                        - ``GBR`` - Data center for the United Kingdom region.
            **Note:** Beta features are subject to change. Please do not use in production
            environments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[TypesPage]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        include=include,
        limit=limit,
        offset=offset,
        x_ads_region=x_ads_region,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: str,
    *,
    client: AuthenticatedClient,
    include: str | Unset = UNSET,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> TypesPage | None:
    """Your GET endpoint

     Retrieves a project’s categories and types.

    Args:
        project_id (str):
        include (str | Unset):
        limit (int | Unset):
        offset (int | Unset):
        x_ads_region (Region | Unset): Specifies where the bucket containing the object is stored.
            Possible values are:
                        - ``US`` - (Default) Data center for the US region.
                        - ``EMEA`` - Data center for the European Union, Middle East, and Africa.
                        - ``AUS`` -  Data center for Australia.
                        - ``CAN`` - Data center for the Canada region.
                        - ``DEU`` - Data center for the Germany region.
                        - ``IND`` - Data center for the India region.
                        - ``JPN`` - Data center for the Japan region.
                        - ``GBR`` - Data center for the United Kingdom region.
            **Note:** Beta features are subject to change. Please do not use in production
            environments.

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        TypesPage
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            client=client,
            include=include,
            limit=limit,
            offset=offset,
            x_ads_region=x_ads_region,
        )
    ).parsed
