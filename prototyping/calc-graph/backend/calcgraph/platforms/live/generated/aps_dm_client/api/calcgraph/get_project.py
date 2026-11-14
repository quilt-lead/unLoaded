from http import HTTPStatus
from typing import Any
from urllib.parse import quote

import httpx

from ... import errors
from ...client import AuthenticatedClient, Client
from ...models.project import Project
from ...types import UNSET, Response, Unset


def _get_kwargs(
    hub_id: str,
    project_id: str,
    *,
    x_user_id: str | Unset = UNSET,
) -> dict[str, Any]:
    headers: dict[str, Any] = {}
    if not isinstance(x_user_id, Unset):
        headers["x-user-id"] = x_user_id

    _kwargs: dict[str, Any] = {
        "method": "get",
        "url": "/project/v1/hubs/{hub_id}/projects/{project_id}".format(
            hub_id=quote(str(hub_id), safe=""),
            project_id=quote(str(project_id), safe=""),
        ),
    }

    _kwargs["headers"] = headers
    return _kwargs


def _parse_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Project | None:
    if response.status_code == 200:
        response_200 = Project.from_dict(response.json())

        return response_200

    if client.raise_on_unexpected_status:
        raise errors.UnexpectedStatus(response.status_code, response.content)
    else:
        return None


def _build_response(
    *, client: AuthenticatedClient | Client, response: httpx.Response
) -> Response[Project]:
    return Response(
        status_code=HTTPStatus(response.status_code),
        content=response.content,
        headers=response.headers,
        parsed=_parse_response(client=client, response=response),
    )


def sync_detailed(
    hub_id: str,
    project_id: str,
    *,
    client: AuthenticatedClient,
    x_user_id: str | Unset = UNSET,
) -> Response[Project]:
    """Get a Project

     Returns the specified project from within the specified hub.

    For BIM 360 Docs, a hub ID corresponds to a BIM 360 account ID. To convert a BIM 360 account ID to a
    hub ID, prefix the account ID with ``b.``. For example, an account ID of ```c8b0c73d-3ae9```
    translates to a hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert a BIM 360 project ID to a Data Management project ID prefix the BIM 360
    Project ID with ``b.``. For example, a project ID of ``c8b0c73d-3ae9`` translates to a project ID of
    ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        project_id (str):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Project]
    """

    kwargs = _get_kwargs(
        hub_id=hub_id,
        project_id=project_id,
        x_user_id=x_user_id,
    )

    response = client.get_httpx_client().request(
        **kwargs,
    )

    return _build_response(client=client, response=response)


def sync(
    hub_id: str,
    project_id: str,
    *,
    client: AuthenticatedClient,
    x_user_id: str | Unset = UNSET,
) -> Project | None:
    """Get a Project

     Returns the specified project from within the specified hub.

    For BIM 360 Docs, a hub ID corresponds to a BIM 360 account ID. To convert a BIM 360 account ID to a
    hub ID, prefix the account ID with ``b.``. For example, an account ID of ```c8b0c73d-3ae9```
    translates to a hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert a BIM 360 project ID to a Data Management project ID prefix the BIM 360
    Project ID with ``b.``. For example, a project ID of ``c8b0c73d-3ae9`` translates to a project ID of
    ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        project_id (str):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Project
    """

    return sync_detailed(
        hub_id=hub_id,
        project_id=project_id,
        client=client,
        x_user_id=x_user_id,
    ).parsed


async def asyncio_detailed(
    hub_id: str,
    project_id: str,
    *,
    client: AuthenticatedClient,
    x_user_id: str | Unset = UNSET,
) -> Response[Project]:
    """Get a Project

     Returns the specified project from within the specified hub.

    For BIM 360 Docs, a hub ID corresponds to a BIM 360 account ID. To convert a BIM 360 account ID to a
    hub ID, prefix the account ID with ``b.``. For example, an account ID of ```c8b0c73d-3ae9```
    translates to a hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert a BIM 360 project ID to a Data Management project ID prefix the BIM 360
    Project ID with ``b.``. For example, a project ID of ``c8b0c73d-3ae9`` translates to a project ID of
    ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        project_id (str):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Response[Project]
    """

    kwargs = _get_kwargs(
        hub_id=hub_id,
        project_id=project_id,
        x_user_id=x_user_id,
    )

    response = await client.get_async_httpx_client().request(**kwargs)

    return _build_response(client=client, response=response)


async def asyncio(
    hub_id: str,
    project_id: str,
    *,
    client: AuthenticatedClient,
    x_user_id: str | Unset = UNSET,
) -> Project | None:
    """Get a Project

     Returns the specified project from within the specified hub.

    For BIM 360 Docs, a hub ID corresponds to a BIM 360 account ID. To convert a BIM 360 account ID to a
    hub ID, prefix the account ID with ``b.``. For example, an account ID of ```c8b0c73d-3ae9```
    translates to a hub ID of ``b.c8b0c73d-3ae9``.

    Similarly, to convert a BIM 360 project ID to a Data Management project ID prefix the BIM 360
    Project ID with ``b.``. For example, a project ID of ``c8b0c73d-3ae9`` translates to a project ID of
    ``b.c8b0c73d-3ae9``.

    **Note:** This operation works with both BIM 360 Projects and Forma Projects.

    Args:
        hub_id (str):
        project_id (str):
        x_user_id (str | Unset):

    Raises:
        errors.UnexpectedStatus: If the server returns an undocumented status code and Client.raise_on_unexpected_status is True.
        httpx.TimeoutException: If the request takes longer than Client.timeout.

    Returns:
        Project
    """

    return (
        await asyncio_detailed(
            hub_id=hub_id,
            project_id=project_id,
            client=client,
            x_user_id=x_user_id,
        )
    ).parsed
