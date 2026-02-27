# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import httpx

from maascommon.enums.openfga import (
    OPENFGA_AUTHORIZATION_MODEL_ID,
    OPENFGA_STORE_ID,
)
from maascommon.openfga.base import BaseOpenFGAClient


class SyncOpenFGAClient(BaseOpenFGAClient):
    """Synchronous client for interacting with OpenFGA API."""

    def __init__(self, unix_socket: str | None = None):
        super().__init__(unix_socket)
        self.client = self._init_client()

    def _init_client(self) -> httpx.Client:
        return httpx.Client(
            timeout=httpx.Timeout(10),
            headers=self.HEADERS,
            base_url="http://unix/",
            transport=httpx.HTTPTransport(uds=self.socket_path),
        )

    def close(self):
        self.client.close()

    def _check(self, user, relation: str, obj: str) -> bool:
        response = self.client.post(
            f"/stores/{OPENFGA_STORE_ID}/check",
            json={
                "tuple_key": {
                    "user": f"user:{user.id}",  # type: ignore[reportAttributeAccessIssue]
                    "relation": relation,
                    "object": obj,
                },
                "authorization_model_id": OPENFGA_AUTHORIZATION_MODEL_ID,
            },
        )
        response.raise_for_status()
        return response.json().get("allowed", False)

    def _list_objects(self, user, relation: str, obj_type: str) -> list[int]:
        response = self.client.post(
            f"/stores/{OPENFGA_STORE_ID}/list-objects",
            json={
                "authorization_model_id": OPENFGA_AUTHORIZATION_MODEL_ID,
                "user": f"user:{user.id}",  # type: ignore[reportAttributeAccessIssue]
                "relation": relation,
                "type": obj_type,
            },
        )
        response.raise_for_status()
        return self._parse_list_objects(response.json())

    # Machine & Pool Permissions
    def can_edit_machines(self, user) -> bool:
        return self._check(user, "can_edit_machines", self.MAAS_GLOBAL_OBJ)

    def can_edit_machines_in_pool(self, user, pool_id: int) -> bool:
        return self._check(
            user, "can_edit_machines", self._format_pool(pool_id)
        )

    def can_deploy_machines_in_pool(self, user, pool_id: int) -> bool:
        return self._check(
            user, "can_deploy_machines", self._format_pool(pool_id)
        )

    def can_view_machines_in_pool(self, user, pool_id: int) -> bool:
        return self._check(
            user, "can_view_machines", self._format_pool(pool_id)
        )

    def can_view_available_machines_in_pool(self, user, pool_id: int) -> bool:
        return self._check(
            user, "can_view_available_machines", self._format_pool(pool_id)
        )

    # Global Permissions
    def can_edit_global_entities(self, user) -> bool:
        return self._check(
            user, "can_edit_global_entities", self.MAAS_GLOBAL_OBJ
        )

    def can_view_global_entities(self, user) -> bool:
        return self._check(
            user, "can_view_global_entities", self.MAAS_GLOBAL_OBJ
        )

    def can_edit_controllers(self, user) -> bool:
        return self._check(user, "can_edit_controllers", self.MAAS_GLOBAL_OBJ)

    def can_view_controllers(self, user) -> bool:
        return self._check(user, "can_view_controllers", self.MAAS_GLOBAL_OBJ)

    def can_edit_identities(self, user) -> bool:
        return self._check(user, "can_edit_identities", self.MAAS_GLOBAL_OBJ)

    def can_view_identities(self, user) -> bool:
        return self._check(user, "can_view_identities", self.MAAS_GLOBAL_OBJ)

    def can_edit_configurations(self, user) -> bool:
        return self._check(
            user, "can_edit_configurations", self.MAAS_GLOBAL_OBJ
        )

    def can_view_configurations(self, user) -> bool:
        return self._check(
            user, "can_view_configurations", self.MAAS_GLOBAL_OBJ
        )

    def can_edit_notifications(self, user) -> bool:
        return self._check(
            user, "can_edit_notifications", self.MAAS_GLOBAL_OBJ
        )

    def can_view_notifications(self, user) -> bool:
        return self._check(
            user, "can_view_notifications", self.MAAS_GLOBAL_OBJ
        )

    def can_edit_boot_entities(self, user) -> bool:
        return self._check(
            user, "can_edit_boot_entities", self.MAAS_GLOBAL_OBJ
        )

    def can_view_boot_entities(self, user) -> bool:
        return self._check(
            user, "can_view_boot_entities", self.MAAS_GLOBAL_OBJ
        )

    def can_edit_license_keys(self, user) -> bool:
        return self._check(user, "can_edit_license_keys", self.MAAS_GLOBAL_OBJ)

    def can_view_license_keys(self, user) -> bool:
        return self._check(user, "can_view_license_keys", self.MAAS_GLOBAL_OBJ)

    def can_view_devices(self, user) -> bool:
        return self._check(user, "can_view_devices", self.MAAS_GLOBAL_OBJ)

    def can_view_ipaddresses(self, user) -> bool:
        return self._check(user, "can_view_ipaddresses", self.MAAS_GLOBAL_OBJ)

    # List Methods
    def list_pools_with_view_machines_access(self, user) -> list[int]:
        return self._list_objects(user, "can_view_machines", "pool")

    def list_pools_with_view_available_machines_access(
        self, user
    ) -> list[int]:
        return self._list_objects(user, "can_view_available_machines", "pool")

    def list_pool_with_deploy_machines_access(self, user) -> list[int]:
        return self._list_objects(user, "can_deploy_machines", "pool")

    def list_pools_with_edit_machines_access(self, user) -> list[int]:
        return self._list_objects(user, "can_edit_machines", "pool")
