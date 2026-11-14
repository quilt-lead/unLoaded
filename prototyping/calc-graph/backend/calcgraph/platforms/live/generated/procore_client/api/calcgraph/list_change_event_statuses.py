from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_change_event_statuses_response_200 import (
    ListChangeEventStatusesResponse200,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    company_id: str,
    *,
    page: int | Unset = UNSET,
    per_page: int | Unset = 10,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["page"] = page

    params["per_page"] = per_page

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v2.0/companies/{company_id}/change_events/statuses".format(
            company_id=quote(str(company_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ListChangeEventStatusesResponse200 | None:
    if response.status_code == 200:
        response_200 = ListChangeEventStatusesResponse200.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ListChangeEventStatusesResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    company_id: str,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = 10,
    procore_company_id: int,
) -> Response[ListChangeEventStatusesResponse200]:
    """List Change Event Statuses

     List All Possible Change Event Statuses for a Specified Company

    Args:
        company_id (str):
        page (int | Unset):
        per_page (int | Unset):  Default: 10.
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListChangeEventStatusesResponse200]
    """

    kwargs = _get_kwargs(
        company_id=company_id,
        page=page,
        per_page=per_page,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    company_id: str,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = 10,
    procore_company_id: int,
) -> ListChangeEventStatusesResponse200 | None:
    """List Change Event Statuses

     List All Possible Change Event Statuses for a Specified Company

    Args:
        company_id (str):
        page (int | Unset):
        per_page (int | Unset):  Default: 10.
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListChangeEventStatusesResponse200
    """

    return sync_detailed(
        company_id=company_id,
        client=client,
        page=page,
        per_page=per_page,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    company_id: str,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = 10,
    procore_company_id: int,
) -> Response[ListChangeEventStatusesResponse200]:
    """List Change Event Statuses

     List All Possible Change Event Statuses for a Specified Company

    Args:
        company_id (str):
        page (int | Unset):
        per_page (int | Unset):  Default: 10.
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ListChangeEventStatusesResponse200]
    """

    kwargs = _get_kwargs(
        company_id=company_id,
        page=page,
        per_page=per_page,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    company_id: str,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = 10,
    procore_company_id: int,
) -> ListChangeEventStatusesResponse200 | None:
    """List Change Event Statuses

     List All Possible Change Event Statuses for a Specified Company

    Args:
        company_id (str):
        page (int | Unset):
        per_page (int | Unset):  Default: 10.
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ListChangeEventStatusesResponse200
    """

    return (
        await asyncio_detailed(
            company_id=company_id,
            client=client,
            page=page,
            per_page=per_page,
            procore_company_id=procore_company_id,
        )
    ).parsed
