# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
from pathlib import Path

import httpx

from maascommon.enums.openfga import (
    OPENFGA_AUTHORIZATION_MODEL_ID,
    OPENFGA_STORE_ID,
)
from maascommon.path import get_maas_data_path


class OpenFGAClient:
    """Client for interacting with OpenFGA API."""

    HEADERS = {"User-Agent": "maas-openfga-client/1.0"}

    def __init__(self, unix_socket: str | None = None):
        self.client = self._create_client(unix_socket)

    def _create_client(
        self, unix_socket: str | None = None
    ) -> httpx.AsyncClient:
        if unix_socket is None:
            unix_socket = str(self._openfga_service_socket_path())

        return httpx.AsyncClient(
            timeout=httpx.Timeout(10),
            headers=self.HEADERS,
            base_url="http://unix/",
            transport=httpx.AsyncHTTPTransport(uds=unix_socket),
        )

    def _openfga_service_socket_path(self) -> Path:
        """Return the path of the socket for the service."""
        return Path(
            os.getenv(
                "MAAS_OPENFGA_HTTP_SOCKET_PATH",
                get_maas_data_path("openfga-http.sock"),
            )
        )

    async def _check(self, tuple_key: dict):
        response = await self.client.post(
            f"/stores/{OPENFGA_STORE_ID}/check",
            json={
                "tuple_key": tuple_key,
                "authorization_model_id": OPENFGA_AUTHORIZATION_MODEL_ID,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("allowed", False)

    async def can_edit_pools(self, user_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_edit_pools",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_view_pools(self, user_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_view_pools",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_edit_machines(self, user_id: str, pool_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_edit_machines",
            "object": f"pool:{pool_id}",
        }
        return await self._check(tuple_key)

    async def can_deploy_machines(self, user_id: str, pool_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_deploy_machines",
            "object": f"pool:{pool_id}",
        }
        return await self._check(tuple_key)

    async def can_view_machines(self, user_id: str, pool_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_view_machines",
            "object": f"pool:{pool_id}",
        }
        return await self._check(tuple_key)

    async def can_view_global_entities(self, user_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_view_global_entities",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_edit_global_entities(self, user_id):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_edit_global_entities",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_view_permissions(self, user_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_view_permissions",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_edit_permissions(self, user_id):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_edit_permissions",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_view_configurations(self, user_id: str):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_view_configurations",
            "object": "maas:0",
        }
        return await self._check(tuple_key)

    async def can_edit_configurations(self, user_id):
        tuple_key = {
            "user": f"user:{user_id}",
            "relation": "can_edit_configurations",
            "object": "maas:0",
        }
        return await self._check(tuple_key)
