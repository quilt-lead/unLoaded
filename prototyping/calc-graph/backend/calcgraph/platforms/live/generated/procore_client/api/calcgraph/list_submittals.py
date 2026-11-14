from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_submittals_response_200_item import ListSubmittalsResponse200Item
from ...models.list_submittals_sort import ListSubmittalsSort
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: int,
    *,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    sort: ListSubmittalsSort | Unset = UNSET,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["page"] = page

    params["per_page"] = per_page

    json_sort: str | Unset = UNSET
    if not isinstance(sort, Unset):
        json_sort = sort.value

    params["sort"] = json_sort

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.1/projects/{project_id}/submittals".format(
            project_id=quote(str(project_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[ListSubmittalsResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ListSubmittalsResponse200Item.from_dict(
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
) -> Response[list[ListSubmittalsResponse200Item]]:
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
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    sort: ListSubmittalsSort | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListSubmittalsResponse200Item]]:
    """List Submittals on a project

     Return a list of all Submittals from a specified Project.
    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        sort (ListSubmittalsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListSubmittalsResponse200Item]]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        page=page,
        per_page=per_page,
        sort=sort,
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
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    sort: ListSubmittalsSort | Unset = UNSET,
    procore_company_id: int,
) -> list[ListSubmittalsResponse200Item] | None:
    """List Submittals on a project

     Return a list of all Submittals from a specified Project.
    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        sort (ListSubmittalsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListSubmittalsResponse200Item]
    """

    return sync_detailed(
        project_id=project_id,
        client=client,
        page=page,
        per_page=per_page,
        sort=sort,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    sort: ListSubmittalsSort | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListSubmittalsResponse200Item]]:
    """List Submittals on a project

     Return a list of all Submittals from a specified Project.
    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        sort (ListSubmittalsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListSubmittalsResponse200Item]]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        page=page,
        per_page=per_page,
        sort=sort,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    sort: ListSubmittalsSort | Unset = UNSET,
    procore_company_id: int,
) -> list[ListSubmittalsResponse200Item] | None:
    """List Submittals on a project

     Return a list of all Submittals from a specified Project.
    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.
    See [Downloading attachments with markup](https://developers.procore.com/reference/rest/document-
    markup#show-or-create-document-markup-downloadable-pdf) for information on downloading attachments
    with markup as a PDF.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        sort (ListSubmittalsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListSubmittalsResponse200Item]
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            client=client,
            page=page,
            per_page=per_page,
            sort=sort,
            procore_company_id=procore_company_id,
        )
    ).parsed
