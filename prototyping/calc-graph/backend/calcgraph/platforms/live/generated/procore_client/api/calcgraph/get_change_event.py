from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.get_change_event_response_200 import GetChangeEventResponse200
from ...models.get_change_event_view import GetChangeEventView
from ...types import UNSET, Response, Unset


def _get_kwargs(
    id: int,
    *,
    project_id: int,
    include_deleted_change_event_line_items: bool | Unset = UNSET,
    view: GetChangeEventView | Unset = UNSET,
    procore_company_id: int,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    headers["Procore-Company-Id"] = str(procore_company_id)

    params: dict[str, Any] = {}

    params["project_id"] = project_id

    params["include_deleted_change_event_line_items"] = (
        include_deleted_change_event_line_items
    )

    json_view: str | Unset = UNSET
    if not isinstance(view, Unset):
        json_view = view.value

    params["view"] = json_view

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/rest/v1.1/change_events/{id}".format(
            id=quote(str(id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> GetChangeEventResponse200 | None:
    if response.status_code == 200:
        response_200 = GetChangeEventResponse200.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[GetChangeEventResponse200]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    id: int,
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    include_deleted_change_event_line_items: bool | Unset = UNSET,
    view: GetChangeEventView | Unset = UNSET,
    procore_company_id: int,
) -> Response[GetChangeEventResponse200]:
    """Show Change Event

     Show Change Event. `view=exclude_change_items` omits change_items, deletable, markup_items,
    individual_markup_rows, and has_edited_markups. Omitting `view`, or sending any other value, returns
    the full Change Event.

    Args:
        id (int):
        project_id (int):
        include_deleted_change_event_line_items (bool | Unset):
        view (GetChangeEventView | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetChangeEventResponse200]
    """

    kwargs = _get_kwargs(
        id=id,
        project_id=project_id,
        include_deleted_change_event_line_items=include_deleted_change_event_line_items,
        view=view,
        procore_company_id=procore_company_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    id: int,
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    include_deleted_change_event_line_items: bool | Unset = UNSET,
    view: GetChangeEventView | Unset = UNSET,
    procore_company_id: int,
) -> GetChangeEventResponse200 | None:
    """Show Change Event

     Show Change Event. `view=exclude_change_items` omits change_items, deletable, markup_items,
    individual_markup_rows, and has_edited_markups. Omitting `view`, or sending any other value, returns
    the full Change Event.

    Args:
        id (int):
        project_id (int):
        include_deleted_change_event_line_items (bool | Unset):
        view (GetChangeEventView | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetChangeEventResponse200
    """

    return sync_detailed(
        id=id,
        client=client,
        project_id=project_id,
        include_deleted_change_event_line_items=include_deleted_change_event_line_items,
        view=view,
        procore_company_id=procore_company_id,
    ).parsed


async def asyncio_detailed(
    id: int,
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    include_deleted_change_event_line_items: bool | Unset = UNSET,
    view: GetChangeEventView | Unset = UNSET,
    procore_company_id: int,
) -> Response[GetChangeEventResponse200]:
    """Show Change Event

     Show Change Event. `view=exclude_change_items` omits change_items, deletable, markup_items,
    individual_markup_rows, and has_edited_markups. Omitting `view`, or sending any other value, returns
    the full Change Event.

    Args:
        id (int):
        project_id (int):
        include_deleted_change_event_line_items (bool | Unset):
        view (GetChangeEventView | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[GetChangeEventResponse200]
    """

    kwargs = _get_kwargs(
        id=id,
        project_id=project_id,
        include_deleted_change_event_line_items=include_deleted_change_event_line_items,
        view=view,
        procore_company_id=procore_company_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    id: int,
    *,
    client: AuthenticatedClient | Client,
    project_id: int,
    include_deleted_change_event_line_items: bool | Unset = UNSET,
    view: GetChangeEventView | Unset = UNSET,
    procore_company_id: int,
) -> GetChangeEventResponse200 | None:
    """Show Change Event

     Show Change Event. `view=exclude_change_items` omits change_items, deletable, markup_items,
    individual_markup_rows, and has_edited_markups. Omitting `view`, or sending any other value, returns
    the full Change Event.

    Args:
        id (int):
        project_id (int):
        include_deleted_change_event_line_items (bool | Unset):
        view (GetChangeEventView | Unset):
        procore_company_id (int):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        GetChangeEventResponse200
    """

    return (
        await asyncio_detailed(
            id=id,
            client=client,
            project_id=project_id,
            include_deleted_change_event_line_items=include_deleted_change_event_line_items,
            view=view,
            procore_company_id=procore_company_id,
        )
    ).parsed
