#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import abc
from http import HTTPStatus
from typing import Any
from urllib.parse import quote

from macaroonbakery.httpbakery.agent import AuthInfo

from maasservicelayer.auth.macaroons.bakery import (
    AsyncAgentInteractor,
    HttpBakeryAsyncClient,
)
from maasservicelayer.auth.macaroons.models.exceptions import (
    MacaroonApiException,
    SyncConflictException,
)
from maasservicelayer.auth.macaroons.models.requests import (
    UpdateResourcesRequest,
)
from maasservicelayer.auth.macaroons.models.responses import (
    GetGroupsResponse,
    PermissionResourcesMapping,
    Resource,
    ResourceListResponse,
    UpdateResourcesResponse,
    UserDetailsResponse,
)
from maasservicelayer.enums.rbac import RbacPermission, RbacResourceType


class MacaroonAsyncClient(abc.ABC):
    """Async client to talk with a macaroon based server."""

    def __init__(self, url: str, auth_info: AuthInfo):
        self._url = url.rstrip("/")
        interactor = AsyncAgentInteractor(auth_info)
        self._client = HttpBakeryAsyncClient(interaction_methods=[interactor])

    @abc.abstractmethod
    async def get_user_details(self, username: str) -> UserDetailsResponse:
        """Return details about a user."""
        return UserDetailsResponse(username=username, fullname="", email="")

    async def _request(
        self, method, url, status_code=200, **kwargs
    ) -> dict[str, Any]:
        resp = await self._client.request(method=method, url=url, **kwargs)
        content = await resp.json()
        if resp.status != status_code:
            # Some servers return "Message" while other "message"
            raise MacaroonApiException(
                resp.status, content.get("Message") or content.get("message")
            )
        return content

    async def close(self):
        await self._client.close()


class CandidAsyncClient(MacaroonAsyncClient):
    """An async client for Candid agent API."""

    def __init__(self, auth_info: AuthInfo):
        url = auth_info.agents[0].url
        super().__init__(url, auth_info)

    async def get_user_details(self, username: str) -> UserDetailsResponse:
        """Return details about a user."""
        url = self._url + quote(f"/v1/u/{username}")
        details = await self._request(method="GET", url=url)
        return UserDetailsResponse.parse_obj(details)

    async def get_groups(self, username: str) -> GetGroupsResponse:
        """Return a list of names for groups a user belongs to."""
        url = self._url + quote(f"/v1/u/{username}/groups")
        groups = await self._request(method="GET", url=url)
        return GetGroupsResponse(groups=groups)


class RbacAsyncClient(MacaroonAsyncClient):
    """An async client for RBAC API."""

    API_BASE_URL = "/api/service/v1"

    def __init__(self, rbac_url: str, auth_info: AuthInfo):
        super().__init__(rbac_url, auth_info)

    def _get_resource_type_url(self, resource_type: RbacResourceType) -> str:
        """Return the URL for `resource_type`."""
        return self._url + quote(
            f"{self.API_BASE_URL}/resources/{resource_type}"
        )

    async def get_user_details(self, username: str) -> UserDetailsResponse:
        """Return details about a user."""
        url = self._url + quote(f"{self.API_BASE_URL}/user/{username}")
        details = await self._request(method="GET", url=url)
        return UserDetailsResponse.parse_obj(details)

    async def get_resources(
        self, resource_type: RbacResourceType
    ) -> ResourceListResponse:
        """Return list of resources with `resource_type`."""
        result = await self._request(
            method="GET", url=self._get_resource_type_url(resource_type)
        )
        return ResourceListResponse(
            resources=[Resource.parse_obj(res) for res in result]
        )

    async def update_resources(
        self,
        resource_type: RbacResourceType,
        request: UpdateResourcesRequest,
    ) -> UpdateResourcesResponse:
        """Put all the resources for `resource_type`.

        This replaces all the resources for `resource_type`.
        """
        try:
            result = await self._request(
                method="POST",
                url=self._get_resource_type_url(resource_type),
                json=request.json(),
            )
        except MacaroonApiException as exc:
            if exc.status == HTTPStatus.CONFLICT and request.last_sync_id:
                # Notify the caller of the conflict explicitly.
                raise SyncConflictException()
            raise
        return UpdateResourcesResponse.parse_obj(result)

    async def allowed_for_user(
        self,
        resource_type: RbacResourceType,
        user: str,
        permissions: set[RbacPermission],
    ) -> list[PermissionResourcesMapping]:
        """Return the resource identifiers that `user` can access with
        `permissions`.

        Returns a dictionary mapping the permissions to the resources of
        `resource_type` that the user can access. An object of `ALL_RESOURCES`
        means the user can access all resources of that type.
        """
        url = self._get_resource_type_url(resource_type) + "/allowed-for-user"

        params = [("u", quote(user))]
        params += [("p", quote(perm)) for perm in permissions]

        result = await self._request(method="GET", url=url, params=params)

        return [
            PermissionResourcesMapping(permission=perm, resources=res)
            for perm, res in result.items()
        ]

    async def is_user_admin(self, user: str) -> bool:
        response = await self.allowed_for_user(
            RbacResourceType.MAAS, user, {RbacPermission.MAAS_ADMIN}
        )
        return response[0].access_all

    async def get_resource_pool_ids(
        self, user: str, permissions: set[RbacPermission]
    ) -> list[PermissionResourcesMapping]:
        return await self.allowed_for_user(
            RbacResourceType.RESOURCE_POOL, user, permissions
        )

    async def can_admin_resource_pools(self, user: str) -> bool:
        response = await self.allowed_for_user(
            RbacResourceType.RESOURCE_POOL, user, {RbacPermission.EDIT}
        )
        return response[0].access_all
