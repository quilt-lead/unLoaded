from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.list_rfis_response_200_item import ListRfisResponse200Item
from ...models.list_rfis_serializer_view import ListRfisSerializerView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    project_id: int,
    *,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    serializer_view: ListRfisSerializerView | Unset = UNSET,
    as_datetimes: bool | Unset = False,
    search: str | Unset = UNSET,
    q: str | Unset = UNSET,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["page"] = page

    params["per_page"] = per_page

    json_serializer_view: str | Unset = UNSET
    if not isinstance(serializer_view, Unset):
        json_serializer_view = serializer_view.value

    params["serializer_view"] = json_serializer_view

    params["as_datetimes"] = as_datetimes

    params["search"] = search

    params["q"] = q

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.0/projects/{project_id}/rfis".format(
            project_id=quote(str(project_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> list[ListRfisResponse200Item] | None:
    if response.status_code == 200:
        response_200 = []
        _response_200 = response.json()
        for response_200_item_data in _response_200:
            response_200_item = ListRfisResponse200Item.from_dict(
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
) -> Response[list[ListRfisResponse200Item]]:
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
    serializer_view: ListRfisSerializerView | Unset = UNSET,
    as_datetimes: bool | Unset = False,
    search: str | Unset = UNSET,
    q: str | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListRfisResponse200Item]]:
    """List RFIs

     Returns all RFIs in a specified Project.

    Use the `serializer_view` query parameter to request alternate list item response shapes for
    existing web or mobile clients.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        serializer_view (ListRfisSerializerView | Unset):
        as_datetimes (bool | Unset):  Default: False.
        search (str | Unset):
        q (str | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListRfisResponse200Item]]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        page=page,
        per_page=per_page,
        serializer_view=serializer_view,
        as_datetimes=as_datetimes,
        search=search,
        q=q,
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
    serializer_view: ListRfisSerializerView | Unset = UNSET,
    as_datetimes: bool | Unset = False,
    search: str | Unset = UNSET,
    q: str | Unset = UNSET,
    procore_company_id: int,
) -> list[ListRfisResponse200Item] | None:
    """List RFIs

     Returns all RFIs in a specified Project.

    Use the `serializer_view` query parameter to request alternate list item response shapes for
    existing web or mobile clients.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        serializer_view (ListRfisSerializerView | Unset):
        as_datetimes (bool | Unset):  Default: False.
        search (str | Unset):
        q (str | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListRfisResponse200Item]
    """

    return sync_detailed(
        project_id=project_id,
        client=client,
        page=page,
        per_page=per_page,
        serializer_view=serializer_view,
        as_datetimes=as_datetimes,
        search=search,
        q=q,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    project_id: int,
    *,
    client: AuthenticatedClient | Client,
    page: int | Unset = UNSET,
    per_page: int | Unset = UNSET,
    serializer_view: ListRfisSerializerView | Unset = UNSET,
    as_datetimes: bool | Unset = False,
    search: str | Unset = UNSET,
    q: str | Unset = UNSET,
    procore_company_id: int,
) -> Response[list[ListRfisResponse200Item]]:
    """List RFIs

     Returns all RFIs in a specified Project.

    Use the `serializer_view` query parameter to request alternate list item response shapes for
    existing web or mobile clients.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        serializer_view (ListRfisSerializerView | Unset):
        as_datetimes (bool | Unset):  Default: False.
        search (str | Unset):
        q (str | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[list[ListRfisResponse200Item]]
    """

    kwargs = _get_kwargs(
        project_id=project_id,
        page=page,
        per_page=per_page,
        serializer_view=serializer_view,
        as_datetimes=as_datetimes,
        search=search,
        q=q,
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
    serializer_view: ListRfisSerializerView | Unset = UNSET,
    as_datetimes: bool | Unset = False,
    search: str | Unset = UNSET,
    q: str | Unset = UNSET,
    procore_company_id: int,
) -> list[ListRfisResponse200Item] | None:
    """List RFIs

     Returns all RFIs in a specified Project.

    Use the `serializer_view` query parameter to request alternate list item response shapes for
    existing web or mobile clients.

    See [Filtering on List Actions](https://developers.procore.com/documentation/filtering-on-list-
    actions) for information on using the filtering capabilities provided by this endpoint.

    Args:
        project_id (int):
        page (int | Unset):
        per_page (int | Unset):
        serializer_view (ListRfisSerializerView | Unset):
        as_datetimes (bool | Unset):  Default: False.
        search (str | Unset):
        q (str | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        list[ListRfisResponse200Item]
    """

    return (
        await asyncio_detailed(
            project_id=project_id,
            client=client,
            page=page,
            per_page=per_page,
            serializer_view=serializer_view,
            as_datetimes=as_datetimes,
            search=search,
            q=q,
            procore_company_id=procore_company_id,
        )
    ).parsed
