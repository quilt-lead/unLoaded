from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.projects_response import ProjectsResponse
from ...types import UNSET, Response, Unset


def _get_kwargs(
    hub_id: str,
    *,
    filterid: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    pagenumber: int | Unset = UNSET,
    pagelimit: int | Unset = UNSET,
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

    json_filterextension_type: list[str] | Unset = UNSET
    if not isinstance(filterextension_type, Unset):
        json_filterextension_type = filterextension_type

    params["filter[extension.type]"] = json_filterextension_type

    params["page[number]"] = pagenumber

    params["page[limit]"] = pagelimit

    params = {k: v for k, v in params.items() if v is not UNSET and v is not None}

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/project/v1/hubs/{hub_id}/projects".format(
            hub_id=quote(str(hub_id), safe=""),
        ),
        "params": params,
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> ProjectsResponse | None:
    if response.status_code == 200:
        response_200 = ProjectsResponse.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[ProjectsResponse]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    hub_id: str,
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    pagenumber: int | Unset = UNSET,
    pagelimit: int | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> Response[ProjectsResponse]:
    """Get Projects

     Returns a collection of active projects within the specified hub. The returned projects can be
    Forma, BIM 360, BIM 360 Team, Fusion Team, and A360 Personal projects.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert BIM 360 or Forma Project IDs to Data Management Project IDs, prefix them with
    ``b.`` For example, a Project ID of `c8b0c73d-3ae9` becomes ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        filterid (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        pagenumber (int | Unset):
        pagelimit (int | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ProjectsResponse]
    """

    kwargs = _get_kwargs(
        hub_id=hub_id,
        filterid=filterid,
        filterextension_type=filterextension_type,
        pagenumber=pagenumber,
        pagelimit=pagelimit,
        x_user_id=x_user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    hub_id: str,
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    pagenumber: int | Unset = UNSET,
    pagelimit: int | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> ProjectsResponse | None:
    """Get Projects

     Returns a collection of active projects within the specified hub. The returned projects can be
    Forma, BIM 360, BIM 360 Team, Fusion Team, and A360 Personal projects.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert BIM 360 or Forma Project IDs to Data Management Project IDs, prefix them with
    ``b.`` For example, a Project ID of `c8b0c73d-3ae9` becomes ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        filterid (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        pagenumber (int | Unset):
        pagelimit (int | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ProjectsResponse
    """

    return sync_detailed(
        hub_id=hub_id,
        client=client,
        filterid=filterid,
        filterextension_type=filterextension_type,
        pagenumber=pagenumber,
        pagelimit=pagelimit,
        x_user_id=x_user_id,
    ).parsed


async def asyncio_detailed(
    hub_id: str,
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    pagenumber: int | Unset = UNSET,
    pagelimit: int | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> Response[ProjectsResponse]:
    """Get Projects

     Returns a collection of active projects within the specified hub. The returned projects can be
    Forma, BIM 360, BIM 360 Team, Fusion Team, and A360 Personal projects.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert BIM 360 or Forma Project IDs to Data Management Project IDs, prefix them with
    ``b.`` For example, a Project ID of `c8b0c73d-3ae9` becomes ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        filterid (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        pagenumber (int | Unset):
        pagelimit (int | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[ProjectsResponse]
    """

    kwargs = _get_kwargs(
        hub_id=hub_id,
        filterid=filterid,
        filterextension_type=filterextension_type,
        pagenumber=pagenumber,
        pagelimit=pagelimit,
        x_user_id=x_user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    hub_id: str,
    *,
    client: AuthenticatedClient,
    filterid: list[str] | Unset = UNSET,
    filterextension_type: list[str] | Unset = UNSET,
    pagenumber: int | Unset = UNSET,
    pagelimit: int | Unset = UNSET,
    x_user_id: str | Unset = UNSET,
) -> ProjectsResponse | None:
    """Get Projects

     Returns a collection of active projects within the specified hub. The returned projects can be
    Forma, BIM 360, BIM 360 Team, Fusion Team, and A360 Personal projects.

    For BIM 360, a Data Management Hub ID corresponds to an Account ID. For Forma, a Data Management Hub
    ID corresponds to a Forma Hub ID. To convert either to a Data Management Hub ID, prefix the ID with
    ``b.`` For example, a BIM 360 Account ID or Forma Hub ID of ``c8b0c73d-3ae9`` translates to a Data
    Management Hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert BIM 360 or Forma Project IDs to Data Management Project IDs, prefix them with
    ``b.`` For example, a Project ID of `c8b0c73d-3ae9` becomes ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        filterid (list[str] | Unset):
        filterextension_type (list[str] | Unset):
        pagenumber (int | Unset):
        pagelimit (int | Unset):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        ProjectsResponse
    """

    return (
        await asyncio_detailed(
            hub_id=hub_id,
            client=client,
            filterid=filterid,
            filterextension_type=filterextension_type,
            pagenumber=pagenumber,
            pagelimit=pagelimit,
            x_user_id=x_user_id,
        )
    ).parsed
