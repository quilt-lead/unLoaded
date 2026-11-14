from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_projects_response_200_item import ListProjectsResponse200Item
from ...models.list_projects_sort import ListProjectsSort
from ...models.list_projects_view import ListProjectsView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    company_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    view: ListProjectsView | Unset = UNSET,
    sort: ListProjectsSort | Unset = UNSET,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["company_id"] = company_id

    params["page"] = page

    params["per_page"] = per_page

    json_view: str | Unset = UNSET
    if not isinstance(view, Unset):
        json_view = view.value

    params["view"] = json_view

    json_sort: str | Unset = UNSET
    if not isinstance(sort, Unset):
        json_sort = sort.value

    params["sort"] = json_sort

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.1/projects",
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[ListProjectsResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ListProjectsResponse200Item.from_dict(
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
) -> Response[list[ListProjectsResponse200Item]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    company_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    view: ListProjectsView | Unset = UNSET,
    sort: ListProjectsSort | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListProjectsResponse200Item]]:
    """List projects

     Return a list of active Projects.

    If the authenticated user has full company admin permissions the request will return all of the
    projects in the company. If the user does not have full company admin permissions, the request will
    only return the projects that the user has been added to.
    The default pagination is 100 projects per page. The max page size is 300 projects due to the size
    of the data in the response.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        company_id (int):
        page (int | Unset):
        per_page (int | Unset):
        view (ListProjectsView | Unset):
        sort (ListProjectsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListProjectsResponse200Item]]
    """

    kwargs = _get_kwargs(
        company_id=company_id,
        page=page,
        per_page=per_page,
        view=view,
        sort=sort,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    company_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    view: ListProjectsView | Unset = UNSET,
    sort: ListProjectsSort | Unset = UNSET,
    procore_company_id: int,
) -> list[ListProjectsResponse200Item] | None:
    """List projects

     Return a list of active Projects.

    If the authenticated user has full company admin permissions the request will return all of the
    projects in the company. If the user does not have full company admin permissions, the request will
    only return the projects that the user has been added to.
    The default pagination is 100 projects per page. The max page size is 300 projects due to the size
    of the data in the response.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        company_id (int):
        page (int | Unset):
        per_page (int | Unset):
        view (ListProjectsView | Unset):
        sort (ListProjectsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListProjectsResponse200Item]
    """

    return sync_detailed(
        client=client,
        company_id=company_id,
        page=page,
        per_page=per_page,
        view=view,
        sort=sort,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    company_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    view: ListProjectsView | Unset = UNSET,
    sort: ListProjectsSort | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListProjectsResponse200Item]]:
    """List projects

     Return a list of active Projects.

    If the authenticated user has full company admin permissions the request will return all of the
    projects in the company. If the user does not have full company admin permissions, the request will
    only return the projects that the user has been added to.
    The default pagination is 100 projects per page. The max page size is 300 projects due to the size
    of the data in the response.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        company_id (int):
        page (int | Unset):
        per_page (int | Unset):
        view (ListProjectsView | Unset):
        sort (ListProjectsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListProjectsResponse200Item]]
    """

    kwargs = _get_kwargs(
        company_id=company_id,
        page=page,
        per_page=per_page,
        view=view,
        sort=sort,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    company_id: int,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    view: ListProjectsView | Unset = UNSET,
    sort: ListProjectsSort | Unset = UNSET,
    procore_company_id: int,
) -> list[ListProjectsResponse200Item] | None:
    """List projects

     Return a list of active Projects.

    If the authenticated user has full company admin permissions the request will return all of the
    projects in the company. If the user does not have full company admin permissions, the request will
    only return the projects that the user has been added to.
    The default pagination is 100 projects per page. The max page size is 300 projects due to the size
    of the data in the response.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        company_id (int):
        page (int | Unset):
        per_page (int | Unset):
        view (ListProjectsView | Unset):
        sort (ListProjectsSort | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListProjectsResponse200Item]
    """

    return (
        await asyncio_detailed(
            client=client,
            company_id=company_id,
            page=page,
            per_page=per_page,
            view=view,
            sort=sort,
            procore_company_id=procore_company_id,
        )
    ).parsed
