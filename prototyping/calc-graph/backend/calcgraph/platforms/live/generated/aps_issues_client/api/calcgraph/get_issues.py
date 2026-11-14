from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.fields import Fields
from ...models.issues import Issues
from ...models.region import Region
from ...models.sort_by import SortBy
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: str,
    *,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    sort_by: list[SortBy] | Unset = UNSET,
    fields: list[Fields] | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_ads_region, Unset):
        headers["x-ads-region"] = str(x_ads_region)

    params: dict[str, Any] = {}

    params["limit"] = limit

    params["offset"] = offset

    json_sort_by: list[str] | Unset = UNSET
    if not isinstance(sort_by, Unset):
        json_sort_by = []
        for componentsschemassort_by_internal_item_data in sort_by:
            componentsschemassort_by_internal_item = (
                componentsschemassort_by_internal_item_data.value
            )
            json_sort_by.append(componentsschemassort_by_internal_item)

    params["sortBy"] = json_sort_by

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
        "url": "/construction/issues/v1/projects/{project_id}/issues".format(
            project_id=quote(str(project_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Issues | None:
    if response.status_code == 200:
        response_200 = Issues.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Issues]:
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
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    sort_by: list[SortBy] | Unset = UNSET,
    fields: list[Fields] | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> Response[Issues]:
    """Your GET endpoint

     Retrieves information about all the issues in a project, including details about their associated
    comments and attachments.

    Args:
        project_id (str):
        limit (int | Unset):
        offset (int | Unset):
        sort_by (list[SortBy] | Unset):
        fields (list[Fields] | Unset):
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
        Response[Issues]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        fields=fields,
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
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    sort_by: list[SortBy] | Unset = UNSET,
    fields: list[Fields] | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> Issues | None:
    """Your GET endpoint

     Retrieves information about all the issues in a project, including details about their associated
    comments and attachments.

    Args:
        project_id (str):
        limit (int | Unset):
        offset (int | Unset):
        sort_by (list[SortBy] | Unset):
        fields (list[Fields] | Unset):
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
        Issues
    """

    return sync_detailed(
        project_id=project_id,
        client=client,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        fields=fields,
        x_ads_region=x_ads_region,
    ).parsed


async def asyncio_detailed(
    project_id: str,
    *,
    client: AuthenticatedClient,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    sort_by: list[SortBy] | Unset = UNSET,
    fields: list[Fields] | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> Response[Issues]:
    """Your GET endpoint

     Retrieves information about all the issues in a project, including details about their associated
    comments and attachments.

    Args:
        project_id (str):
        limit (int | Unset):
        offset (int | Unset):
        sort_by (list[SortBy] | Unset):
        fields (list[Fields] | Unset):
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
        Response[Issues]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        limit=limit,
        offset=offset,
        sort_by=sort_by,
        fields=fields,
        x_ads_region=x_ads_region,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: str,
    *,
    client: AuthenticatedClient,
    limit: int | Unset = UNSET,
    offset: int | Unset = UNSET,
    sort_by: list[SortBy] | Unset = UNSET,
    fields: list[Fields] | Unset = UNSET,
    x_ads_region: Region | Unset = UNSET,
) -> Issues | None:
    """Your GET endpoint

     Retrieves information about all the issues in a project, including details about their associated
    comments and attachments.

    Args:
        project_id (str):
        limit (int | Unset):
        offset (int | Unset):
        sort_by (list[SortBy] | Unset):
        fields (list[Fields] | Unset):
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
        Issues
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            client=client,
            limit=limit,
            offset=offset,
            sort_by=sort_by,
            fields=fields,
            x_ads_region=x_ads_region,
        )
    ).parsed
