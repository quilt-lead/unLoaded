from http import HTTPStatus
from typing import Any

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.hubs_response import HubsResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    *,
    filterid: list[str] | Unset = UNSET,
    filtername: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_user_id, Unset):
        headers["x-user-id"] = x_user_id

    params: dict[str, Any] = {}

    json_filterid: list[str] | Unset = UNSET
    if not isinstance(filterid, Unset):
        json_filterid = filterid

    params["filter[id]"] = json_filterid

    json_filtername: list[str] | Unset = UNSET
    if not isinstance(filtername, Unset):
        json_filtername = filtername

    params["filter[name]"] = json_filtername

    json_filterextension_type: list[str] | Unset = UNSET
    if not isinstance(filterextension_type, Unset):
        json_filterextension_type = filterextension_type

    params["filter[extension.type]"] = json_filterextension_type

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/project/v1/hubs",
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> HubsResponse | None:
    if response.status_code == 200:
        response_200 = HubsResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[HubsResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filtername: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> Response[HubsResponse]:
    """List Hubs

     Returns a collection of hubs that the user of your app can access.

    The returned hubs can be BIM 360 Team hubs, Fusion Team hubs, A360 Personal hubs, Forma Data
    Management accounts, or BIM 360 Docs accounts. Only active hubs are returned.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        filterid (list[str] | Unset):
        filtername (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HubsResponse]
    """

    kwargs = _get_kwargs(
        filterid=filterid,
        filtername=filtername,
        filterextension_type=filterextension_type,
        x_user_id=x_user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filtername: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> HubsResponse | None:
    """List Hubs

     Returns a collection of hubs that the user of your app can access.

    The returned hubs can be BIM 360 Team hubs, Fusion Team hubs, A360 Personal hubs, Forma Data
    Management accounts, or BIM 360 Docs accounts. Only active hubs are returned.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        filterid (list[str] | Unset):
        filtername (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HubsResponse
    """

    return sync_detailed(
        client=client,
        filterid=filterid,
        filtername=filtername,
        filterextension_type=filterextension_type,
        x_user_id=x_user_id,
    ).parsed


async def asyncio_detailed(
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filtername: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> Response[HubsResponse]:
    """List Hubs

     Returns a collection of hubs that the user of your app can access.

    The returned hubs can be BIM 360 Team hubs, Fusion Team hubs, A360 Personal hubs, Forma Data
    Management accounts, or BIM 360 Docs accounts. Only active hubs are returned.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        filterid (list[str] | Unset):
        filtername (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[HubsResponse]
    """

    kwargs = _get_kwargs(
        filterid=filterid,
        filtername=filtername,
        filterextension_type=filterextension_type,
        x_user_id=x_user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filtername: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> HubsResponse | None:
    """List Hubs

     Returns a collection of hubs that the user of your app can access.

    The returned hubs can be BIM 360 Team hubs, Fusion Team hubs, A360 Personal hubs, Forma Data
    Management accounts, or BIM 360 Docs accounts. Only active hubs are returned.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        filterid (list[str] | Unset):
        filtername (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        HubsResponse
    """

    return (
        await asyncio_detailed(
            client=client,
            filterid=filterid,
            filtername=filtername,
            filterextension_type=filterextension_type,
            x_user_id=x_user_id,
        )
    ).parsed
