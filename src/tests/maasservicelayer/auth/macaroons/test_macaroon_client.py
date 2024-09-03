#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from http import HTTPStatus

from macaroonbakery import bakery
from macaroonbakery.httpbakery.agent import Agent, AuthInfo
import pytest

from maasservicelayer.auth.macaroons.macaroon_client import (
    CandidAsyncClient,
    RbacAsyncClient,
)
from maasservicelayer.auth.macaroons.models.base import Resource
from maasservicelayer.auth.macaroons.models.exceptions import (
    MacaroonApiException,
    SyncConflictException,
)
from maasservicelayer.auth.macaroons.models.requests import (
    UpdateResourcesRequest,
)
from maasservicelayer.auth.macaroons.models.responses import (
    AllowedForUserResponse,
    GetGroupsResponse,
    PermissionResourcesMapping,
    ResourceListResponse,
    UpdateResourcesResponse,
    UserDetailsResponse,
)


@pytest.fixture
def auth_info() -> AuthInfo:
    config = {
        "url": "https://auth.example.com",
        "user": "user@candid",
        "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
    }
    key = bakery.PrivateKey.deserialize(config["key"])
    agent = Agent(
        url=config["url"],
        username=config["user"],
    )
    return AuthInfo(key=key, agents=[agent])


@pytest.fixture
async def candid_client(auth_info) -> CandidAsyncClient:
    return CandidAsyncClient(auth_info=auth_info)


@pytest.fixture
async def rbac_client(auth_info) -> RbacAsyncClient:
    return RbacAsyncClient(
        rbac_url="https://rbac.example.com", auth_info=auth_info
    )


RBAC_BASE_URL = "https://rbac.example.com/api/service/v1"


@pytest.mark.asyncio
class TestCandidAsyncClient:
    async def test_get_groups(self, candid_client, mock_aioresponse):
        expected_response = ["group1", "group2"]
        mock_aioresponse.get(
            "https://auth.example.com/v1/u/foo/groups",
            payload=expected_response,
        )
        resp = await candid_client.get_groups("foo")
        assert resp == GetGroupsResponse(groups=expected_response)
        mock_aioresponse.assert_called_with(
            method="GET",
            url="https://auth.example.com/v1/u/foo/groups",
        )

    async def test_get_groups_user_not_found(
        self, candid_client, mock_aioresponse
    ):
        resp = {
            "code": "not found",
            "messsage": "user foo not found",
        }
        mock_aioresponse.get(
            "https://auth.example.com/v1/u/foo/groups",
            payload=resp,
            status=404,
        )
        with pytest.raises(MacaroonApiException) as exc:
            await candid_client.get_groups("foo")
        assert exc.value.status == 404
        mock_aioresponse.assert_called_with(
            method="GET",
            url="https://auth.example.com/v1/u/foo/groups",
        )


@pytest.mark.asyncio
class TestRbacAsyncClient:
    async def test_get_user(self, rbac_client, mock_aioresponse):
        expected_response = {
            "username": "user",
            "fullname": "A user",
            "email": "user@example.com",
        }
        mock_aioresponse.get(
            f"{RBAC_BASE_URL}/user/user", payload=expected_response
        )
        response = await rbac_client.get_user_details("user")
        assert response == UserDetailsResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"{RBAC_BASE_URL}/user/user",
        )

    async def test_get_resources(self, rbac_client, mock_aioresponse):
        expected_response = [
            {"identifier": "1", "name": "pool-1"},
            {"identifier": "2", "name": "pool-2"},
        ]
        mock_aioresponse.get(
            f"{RBAC_BASE_URL}/resources/resource-pool",
            payload=expected_response,
        )

        resp = await rbac_client.get_resources("resource-pool")
        resources = [Resource.parse_obj(res) for res in expected_response]
        assert resp == ResourceListResponse(resources=resources)
        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"{RBAC_BASE_URL}/resources/resource-pool",
        )

    async def test_update_resources(self, rbac_client, mock_aioresponse):
        updates = [
            Resource(identifier="1", name="pool-1"),
            Resource(identifier="2", name="pool-2"),
        ]
        removals = [11, 22, 33]
        req = UpdateResourcesRequest(
            updates=updates, removals=removals, last_sync_id="a-b-c"
        )
        expected_response = {"sync-id": "x-y-z"}
        mock_aioresponse.post(
            f"{RBAC_BASE_URL}/resources/resource-pool",
            payload=expected_response,
        )

        resp = await rbac_client.update_resources("resource-pool", req)

        assert resp == UpdateResourcesResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_once_with(
            method="POST",
            url=f"{RBAC_BASE_URL}/resources/resource-pool",
            json=req.json(),
        )

    async def test_update_resources_no_sync_id(
        self, rbac_client, mock_aioresponse
    ):
        updates = [
            Resource(identifier="1", name="pool-1"),
            Resource(identifier="2", name="pool-2"),
        ]
        removals = [11, 22, 33]
        req = UpdateResourcesRequest(
            updates=updates,
            removals=removals,
        )
        expected_response = {"sync-id": "x-y-z"}
        mock_aioresponse.post(
            f"{RBAC_BASE_URL}/resources/resource-pool",
            payload=expected_response,
        )

        resp = await rbac_client.update_resources("resource-pool", req)
        assert resp == UpdateResourcesResponse.parse_obj(expected_response)
        mock_aioresponse.assert_called_once_with(
            method="POST",
            url=f"{RBAC_BASE_URL}/resources/resource-pool",
            json=req.json(),
        )

    async def test_update_resources_sync_conflict(
        self, rbac_client, mock_aioresponse
    ):
        updates = [
            Resource(identifier="1", name="pool-1"),
            Resource(identifier="2", name="pool-2"),
        ]
        removals = [11, 22, 33]
        req = UpdateResourcesRequest(
            updates=updates, removals=removals, last_sync_id="a-b-c"
        )
        expected_response = {"sync-id": "x-y-z"}
        mock_aioresponse.post(
            f"{RBAC_BASE_URL}/resources/resource-pool",
            payload=expected_response,
            status=HTTPStatus.CONFLICT,
        )

        with pytest.raises(SyncConflictException):
            await rbac_client.update_resources("resource-pool", req)

        mock_aioresponse.assert_called_once_with(
            method="POST",
            url=f"{RBAC_BASE_URL}/resources/resource-pool",
            json=req.json(),
        )

    async def test_allowed_for_user_all_resources(
        self, rbac_client, mock_aioresponse
    ):
        expected_response = {"admin": [""]}

        mock_aioresponse.get(
            f"{RBAC_BASE_URL}/resources/resource-pool/allowed-for-user?u=user&p=admin",
            payload=expected_response,
        )

        resp = await rbac_client.allowed_for_user(
            "resource-pool", "user", ["admin"]
        )

        perms = [
            PermissionResourcesMapping(permission=perm, resources=res)
            for perm, res in expected_response.items()
        ]

        assert resp == AllowedForUserResponse(permissions=perms)
        assert resp.permissions[0].access_all is True
        assert resp.permissions[0].resources is None
        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"{RBAC_BASE_URL}/resources/resource-pool/allowed-for-user",
            params=[("u", "user"), ("p", "admin")],
        )

    async def test_allowed_for_user_resource_ids(
        self, rbac_client, mock_aioresponse
    ):
        expected_response = {"admin": ["1", "2", "3"]}

        mock_aioresponse.get(
            f"{RBAC_BASE_URL}/resources/resource-pool/allowed-for-user?u=user&p=admin",
            payload=expected_response,
        )

        resp = await rbac_client.allowed_for_user(
            "resource-pool", "user", ["admin"]
        )
        perms = [
            PermissionResourcesMapping(permission=perm, resources=res)
            for perm, res in expected_response.items()
        ]

        assert resp == AllowedForUserResponse(permissions=perms)
        assert resp.permissions[0].access_all is False
        assert resp.permissions[0].resources == [1, 2, 3]
        mock_aioresponse.assert_called_once_with(
            method="GET",
            url=f"{RBAC_BASE_URL}/resources/resource-pool/allowed-for-user",
            params=[("u", "user"), ("p", "admin")],
        )
