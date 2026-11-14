from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.create_submittal_body import CreateSubmittalBody
from ...models.create_submittal_response_201 import CreateSubmittalResponse201
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: int,
    *,
    body: CreateSubmittalBody,
    send_emails: bool | Unset = UNSET,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["send_emails"] = send_emails

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "post",
        "url": "/rest/v1.1/projects/{project_id}/submittals".format(
            project_id=quote(str(project_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["json"] = body.to_dict()

    headers["Content-Type"] = "application/json"

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> CreateSubmittalResponse201 | None:
    if response.status_code == 201:
        response_201 = CreateSubmittalResponse201.from_dict(response.json())

        return response_201

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[CreateSubmittalResponse201]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: CreateSubmittalBody,
    send_emails: bool | Unset = UNSET,
    procore_company_id: int,
) -> Response[CreateSubmittalResponse201]:
    """Create Submittal

     Create a new Submittal associated with the specified Project.

    Args:
        project_id (int):
        send_emails (bool | Unset):
        procore_company_id (int):
        body (CreateSubmittalBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateSubmittalResponse201]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        body=body,
        send_emails=send_emails,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: CreateSubmittalBody,
    send_emails: bool | Unset = UNSET,
    procore_company_id: int,
) -> CreateSubmittalResponse201 | None:
    """Create Submittal

     Create a new Submittal associated with the specified Project.

    Args:
        project_id (int):
        send_emails (bool | Unset):
        procore_company_id (int):
        body (CreateSubmittalBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateSubmittalResponse201
    """

    return sync_detailed(
        project_id=project_id,
        client=client,
        body=body,
        send_emails=send_emails,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: CreateSubmittalBody,
    send_emails: bool | Unset = UNSET,
    procore_company_id: int,
) -> Response[CreateSubmittalResponse201]:
    """Create Submittal

     Create a new Submittal associated with the specified Project.

    Args:
        project_id (int):
        send_emails (bool | Unset):
        procore_company_id (int):
        body (CreateSubmittalBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[CreateSubmittalResponse201]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        body=body,
        send_emails=send_emails,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    body: CreateSubmittalBody,
    send_emails: bool | Unset = UNSET,
    procore_company_id: int,
) -> CreateSubmittalResponse201 | None:
    """Create Submittal

     Create a new Submittal associated with the specified Project.

    Args:
        project_id (int):
        send_emails (bool | Unset):
        procore_company_id (int):
        body (CreateSubmittalBody):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        CreateSubmittalResponse201
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            client=client,
            body=body,
            send_emails=send_emails,
            procore_company_id=procore_company_id,
        )
    ).parsed
