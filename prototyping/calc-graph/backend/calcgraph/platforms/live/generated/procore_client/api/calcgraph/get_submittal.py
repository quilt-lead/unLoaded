from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_submittal_response_200 import GetSubmittalResponse200
from ...types import Response


def _get_kwargs(
    project_id: int,
    id: int,
    *,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.1/projects/{project_id}/submittals/{id}".format(
            project_id=quote(str(project_id), safe=""),
            id=quote(str(id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> GetSubmittalResponse200 | None:
    if response.status_code == 200:
        response_200 = GetSubmittalResponse200.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[GetSubmittalResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    project_id: int,
    id: int,
    *,
    client: AuthenticatedClient | Client,
    procore_company_id: int,
) -> Response[GetSubmittalResponse200]:
    """Show Submittal

     Return detailed information on the specified Submittal.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        id (int):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetSubmittalResponse200]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        id=id,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    project_id: int,
    id: int,
    *,
    client: AuthenticatedClient | Client,
    procore_company_id: int,
) -> GetSubmittalResponse200 | None:
    """Show Submittal

     Return detailed information on the specified Submittal.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        id (int):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetSubmittalResponse200
    """

    return sync_detailed(
        project_id=project_id,
        id=id,
        client=client,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    project_id: int,
    id: int,
    *,
    client: AuthenticatedClient | Client,
    procore_company_id: int,
) -> Response[GetSubmittalResponse200]:
    """Show Submittal

     Return detailed information on the specified Submittal.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        id (int):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetSubmittalResponse200]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        id=id,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: int,
    id: int,
    *,
    client: AuthenticatedClient | Client,
    procore_company_id: int,
) -> GetSubmittalResponse200 | None:
    """Show Submittal

     Return detailed information on the specified Submittal.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        id (int):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetSubmittalResponse200
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            id=id,
            client=client,
            procore_company_id=procore_company_id,
        )
    ).parsed
