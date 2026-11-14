from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.issue import Issue
from ...models.region import Region
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: str,
    issue_id: str,
    *,
    x_ads_region: Region | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_ads_region, Unset):
        headers["x-ads-region"] = str(x_ads_region)

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/construction/issues/v1/projects/{project_id}/issues/{issue_id}".format(
            project_id=quote(str(project_id), safe=""),
            issue_id=quote(str(issue_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Issue | None:
    if response.status_code == 200:
        response_200 = Issue.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Issue]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    project_id: str,
    issue_id: str,
    *,
    client: AuthenticatedClient,
    x_ads_region: Region | Unset = UNSET,
) -> Response[Issue]:
    """Your GET endpoint

     Retrieves detailed information about a single issue. For general information about all the issues in
    a project.

    Args:
        project_id (str):
        issue_id (str):
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
        Response[Issue]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        issue_id=issue_id,
        x_ads_region=x_ads_region,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    project_id: str,
    issue_id: str,
    *,
    client: AuthenticatedClient,
    x_ads_region: Region | Unset = UNSET,
) -> Issue | None:
    """Your GET endpoint

     Retrieves detailed information about a single issue. For general information about all the issues in
    a project.

    Args:
        project_id (str):
        issue_id (str):
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
        Issue
    """

    return sync_detailed(
        project_id=project_id,
        issue_id=issue_id,
        client=client,
        x_ads_region=x_ads_region,
    ).parsed


async def asyncio_detailed(
    project_id: str,
    issue_id: str,
    *,
    client: AuthenticatedClient,
    x_ads_region: Region | Unset = UNSET,
) -> Response[Issue]:
    """Your GET endpoint

     Retrieves detailed information about a single issue. For general information about all the issues in
    a project.

    Args:
        project_id (str):
        issue_id (str):
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
        Response[Issue]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        issue_id=issue_id,
        x_ads_region=x_ads_region,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: str,
    issue_id: str,
    *,
    client: AuthenticatedClient,
    x_ads_region: Region | Unset = UNSET,
) -> Issue | None:
    """Your GET endpoint

     Retrieves detailed information about a single issue. For general information about all the issues in
    a project.

    Args:
        project_id (str):
        issue_id (str):
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
        Issue
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            issue_id=issue_id,
            client=client,
            x_ads_region=x_ads_region,
        )
    ).parsed
