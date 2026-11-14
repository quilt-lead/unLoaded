from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_change_event_body import CreateChangeEventBody
from ...models.create_change_event_response_201 import CreateChangeEventResponse201
from ...types import UNSET, Response


def _get_kwargs(
    *,
    body: CreateChangeEventBody,
    project_id: int,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["project_id"] = project_id

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/rest/v1.1/change_events",
        "params": params,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CreateChangeEventResponse201 | None:
    if response.status_code == 201:
        response_201 = CreateChangeEventResponse201.from_dict(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CreateChangeEventResponse201]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateChangeEventBody,
    project_id: int,
    procore_company_id: int,
) -> Response[CreateChangeEventResponse201]:
    """Create Change Event

     Create Change Event.
    `status.id` must identify a Change Event status that exists for the company. Unknown status IDs
    return 400.

    Args:
        project_id (int):
        procore_company_id (int):
        body (CreateChangeEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateChangeEventResponse201]
    """

    kwargs = _get_kwargs(
        body=body,
        project_id=project_id,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    body: CreateChangeEventBody,
    project_id: int,
    procore_company_id: int,
) -> CreateChangeEventResponse201 | None:
    """Create Change Event

     Create Change Event.
    `status.id` must identify a Change Event status that exists for the company. Unknown status IDs
    return 400.

    Args:
        project_id (int):
        procore_company_id (int):
        body (CreateChangeEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateChangeEventResponse201
    """

    return sync_detailed(
        client=client,
        body=body,
        project_id=project_id,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    body: CreateChangeEventBody,
    project_id: int,
    procore_company_id: int,
) -> Response[CreateChangeEventResponse201]:
    """Create Change Event

     Create Change Event.
    `status.id` must identify a Change Event status that exists for the company. Unknown status IDs
    return 400.

    Args:
        project_id (int):
        procore_company_id (int):
        body (CreateChangeEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateChangeEventResponse201]
    """

    kwargs = _get_kwargs(
        body=body,
        project_id=project_id,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    body: CreateChangeEventBody,
    project_id: int,
    procore_company_id: int,
) -> CreateChangeEventResponse201 | None:
    """Create Change Event

     Create Change Event.
    `status.id` must identify a Change Event status that exists for the company. Unknown status IDs
    return 400.

    Args:
        project_id (int):
        procore_company_id (int):
        body (CreateChangeEventBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateChangeEventResponse201
    """

    return (
        await asyncio_detailed(
            client=client,
            body=body,
            project_id=project_id,
            procore_company_id=procore_company_id,
        )
    ).parsed
