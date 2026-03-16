# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import httpx

from maascommon.enums.openfga import (
    OPENFGA_AUTHORIZATION_MODEL_ID,
    OPENFGA_STORE_ID,
)
from maascommon.openfga.base import (
    BaseOpenFGAClient,
    MAASResourceEntitlement,
    OpenFGAEntitlementResourceType,
    PoolResourceEntitlements,
)


class OpenFGAClient(BaseOpenFGAClient):
    """Asynchronous client for interacting with OpenFGA API."""

    def __init__(self, unix_socket: str | None = None):
        super().__init__(unix_socket)
        self.client = self._init_client()

    def _init_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(10),
            headers=self.HEADERS,
            base_url="http://unix/",
            transport=httpx.AsyncHTTPTransport(uds=self.socket_path),
        )

    async def close(self):
        await self.client.aclose()

    async def _check(self, user_id: int, relation: str, obj: str) -> bool:
        response = await self.client.post(
            f"/stores/{OPENFGA_STORE_ID}/check",
            json={
                "tuple_key": {
                    "user": f"user:{user_id}",
                    "relation": relation,
                    "object": obj,
                },
                "authorization_model_id": OPENFGA_AUTHORIZATION_MODEL_ID,
            },
        )
        response.raise_for_status()
        return response.json().get("allowed", False)

    async def _list_objects(
        self, user_id: int, relation: str, obj_type: str
    ) -> list[int]:
        response = await self.client.post(
            f"/stores/{OPENFGA_STORE_ID}/list-objects",
            json={
                "authorization_model_id": OPENFGA_AUTHORIZATION_MODEL_ID,
                "user": f"user:{user_id}",
                "relation": relation,
                "type": obj_type,
            },
        )
        response.raise_for_status()
        return self._parse_list_objects(response.json())

    async def has_permission_on_maas(
        self, permission: MAASResourceEntitlement, user_id: int
    ) -> bool:
        return await self._check(user_id, permission, self.MAAS_GLOBAL_OBJ)

    # Machine & Pool Permissions
    async def can_edit_machines(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_MACHINES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_machines_in_pool(
        self, user_id: int, pool_id: int
    ) -> bool:
        return await self._check(
            user_id,
            PoolResourceEntitlements.CAN_EDIT_MACHINES,
            self._format_pool(pool_id),
        )

    async def can_deploy_machines_in_pool(
        self, user_id: int, pool_id: int
    ) -> bool:
        return await self._check(
            user_id,
            PoolResourceEntitlements.CAN_DEPLOY_MACHINES,
            self._format_pool(pool_id),
        )

    async def can_view_machines_in_pool(
        self, user_id: int, pool_id: int
    ) -> bool:
        return await self._check(
            user_id,
            PoolResourceEntitlements.CAN_VIEW_MACHINES,
            self._format_pool(pool_id),
        )

    async def can_view_available_machines_in_pool(
        self, user_id: int, pool_id: int
    ) -> bool:
        return await self._check(
            user_id,
            PoolResourceEntitlements.CAN_VIEW_AVAILABLE_MACHINES,
            self._format_pool(pool_id),
        )

    # Global Permissions
    async def can_edit_global_entities(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_GLOBAL_ENTITIES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_global_entities(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_GLOBAL_ENTITIES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_controllers(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_CONTROLLERS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_controllers(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_CONTROLLERS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_identities(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_IDENTITIES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_identities(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_IDENTITIES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_configurations(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_CONFIGURATIONS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_configurations(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_CONFIGURATIONS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_notifications(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_NOTIFICATIONS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_notifications(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_NOTIFICATIONS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_boot_entities(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_BOOT_ENTITIES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_boot_entities(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_BOOT_ENTITIES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_edit_license_keys(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_EDIT_LICENSE_KEYS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_license_keys(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_LICENCE_KEYS,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_devices(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_DEVICES,
            self.MAAS_GLOBAL_OBJ,
        )

    async def can_view_ipaddresses(self, user_id: int) -> bool:
        return await self._check(
            user_id,
            MAASResourceEntitlement.CAN_VIEW_IPADDRESSES,
            self.MAAS_GLOBAL_OBJ,
        )

    # List Methods
    async def list_pools_with_view_machines_access(
        self, user_id: int
    ) -> list[int]:
        return await self._list_objects(
            user_id,
            PoolResourceEntitlements.CAN_VIEW_MACHINES,
            OpenFGAEntitlementResourceType.POOL,
        )

    async def list_pools_with_view_available_machines_access(
        self, user_id: int
    ) -> list[int]:
        return await self._list_objects(
            user_id,
            PoolResourceEntitlements.CAN_VIEW_AVAILABLE_MACHINES,
            OpenFGAEntitlementResourceType.POOL,
        )

    async def list_pool_with_deploy_machines_access(
        self, user_id: int
    ) -> list[int]:
        return await self._list_objects(
            user_id,
            PoolResourceEntitlements.CAN_DEPLOY_MACHINES,
            OpenFGAEntitlementResourceType.POOL,
        )

    async def list_pools_with_edit_machines_access(
        self, user_id: int
    ) -> list[int]:
        return await self._list_objects(
            user_id,
            PoolResourceEntitlements.CAN_EDIT_MACHINES,
            OpenFGAEntitlementResourceType.POOL,
        )
