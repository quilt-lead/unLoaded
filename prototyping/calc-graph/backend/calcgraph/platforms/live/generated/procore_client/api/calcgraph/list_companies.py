from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_companies_response_200_item import ListCompaniesResponse200Item
from ...models.list_companies_view import ListCompaniesView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    include_free_companies: bool | Unset = UNSET,
    all_: bool | Unset = UNSET,
    view: ListCompaniesView | Unset = UNSET,
) -> dict[str, Any]:

    params: dict[str, Any] = {}

    params["page"] = page

    params["per_page"] = per_page

    params["include_free_companies"] = include_free_companies

    params["all"] = all_

    json_view: str | Unset = UNSET
    if not isinstance(view, Unset):
        json_view = view.value

    params["view"] = json_view

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.0/companies",
        "params": params,
    }

    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[ListCompaniesResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ListCompaniesResponse200Item.from_dict(
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
) -> Response[list[ListCompaniesResponse200Item]]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    include_free_companies: bool | Unset = UNSET,
    all_: bool | Unset = UNSET,
    view: ListCompaniesView | Unset = UNSET,
) -> Response[list[ListCompaniesResponse200Item]]:
    """List Companies

     Returns companies visible to the current user.

    NOTE: This endpoint does not require the ['Procore-Company-Id' header]
    (https://developers.procore.com/documentation/tutorial-mpz)
    to be included on a request.

    Args:
        page (int | Unset):
        per_page (int | Unset):
        include_free_companies (bool | Unset):
        all_ (bool | Unset):
        view (ListCompaniesView | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListCompaniesResponse200Item]]
    """

    kwargs = _get_kwargs(
        page=page,
        per_page=per_page,
        include_free_companies=include_free_companies,
        all_=all_,
        view=view,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    include_free_companies: bool | Unset = UNSET,
    all_: bool | Unset = UNSET,
    view: ListCompaniesView | Unset = UNSET,
) -> list[ListCompaniesResponse200Item] | None:
    """List Companies

     Returns companies visible to the current user.

    NOTE: This endpoint does not require the ['Procore-Company-Id' header]
    (https://developers.procore.com/documentation/tutorial-mpz)
    to be included on a request.

    Args:
        page (int | Unset):
        per_page (int | Unset):
        include_free_companies (bool | Unset):
        all_ (bool | Unset):
        view (ListCompaniesView | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListCompaniesResponse200Item]
    """

    return sync_detailed(
        client=client,
        page=page,
        per_page=per_page,
        include_free_companies=include_free_companies,
        all_=all_,
        view=view,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    include_free_companies: bool | Unset = UNSET,
    all_: bool | Unset = UNSET,
    view: ListCompaniesView | Unset = UNSET,
) -> Response[list[ListCompaniesResponse200Item]]:
    """List Companies

     Returns companies visible to the current user.

    NOTE: This endpoint does not require the ['Procore-Company-Id' header]
    (https://developers.procore.com/documentation/tutorial-mpz)
    to be included on a request.

    Args:
        page (int | Unset):
        per_page (int | Unset):
        include_free_companies (bool | Unset):
        all_ (bool | Unset):
        view (ListCompaniesView | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListCompaniesResponse200Item]]
    """

    kwargs = _get_kwargs(
        page=page,
        per_page=per_page,
        include_free_companies=include_free_companies,
        all_=all_,
        view=view,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    include_free_companies: bool | Unset = UNSET,
    all_: bool | Unset = UNSET,
    view: ListCompaniesView | Unset = UNSET,
) -> list[ListCompaniesResponse200Item] | None:
    """List Companies

     Returns companies visible to the current user.

    NOTE: This endpoint does not require the ['Procore-Company-Id' header]
    (https://developers.procore.com/documentation/tutorial-mpz)
    to be included on a request.

    Args:
        page (int | Unset):
        per_page (int | Unset):
        include_free_companies (bool | Unset):
        all_ (bool | Unset):
        view (ListCompaniesView | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListCompaniesResponse200Item]
    """

    return (
        await asyncio_detailed(
            client=client,
            page=page,
            per_page=per_page,
            include_free_companies=include_free_companies,
            all_=all_,
            view=view,
        )
    ).parsed
