from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_change_events_response_200_item import (
    ListChangeEventsResponse200Item,
)
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    project_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["project_id"] = project_id

    params["page"] = page

    params["per_page"] = per_page

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.1/change_events",
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[ListChangeEventsResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ListChangeEventsResponse200Item.from_dict(
                response_200_item_data
            )

            response_200.append(response_200_item)

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[list[ListChangeEventsResponse200Item]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListChangeEventsResponse200Item]]:
    """List Change Events

     List Change Events.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListChangeEventsResponse200Item]]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        page=page,
        per_page=per_page,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    procore_company_id: int,
) -> list[ListChangeEventsResponse200Item] | None:
    """List Change Events

     List Change Events.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListChangeEventsResponse200Item]
    """

    return sync_detailed(
        client=client,
        project_id=project_id,
        page=page,
        per_page=per_page,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListChangeEventsResponse200Item]]:
    """List Change Events

     List Change Events.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListChangeEventsResponse200Item]]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        page=page,
        per_page=per_page,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    procore_company_id: int,
) -> list[ListChangeEventsResponse200Item] | None:
    """List Change Events

     List Change Events.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListChangeEventsResponse200Item]
    """

    return (
        await asyncio_detailed(
            client=client,
            project_id=project_id,
            page=page,
            per_page=per_page,
            procore_company_id=procore_company_id,
        )
    ).parsed
