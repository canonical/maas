# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.db import connection

from maascommon.openfga.sync_client import SyncOpenFGAClient


class OpenFGAClientMock(SyncOpenFGAClient):
    # Methods allowing access ONLY to superusers
    SUPERUSER_ONLY = [
        "can_edit_machines",
        "can_edit_machines_in_pool",
        "can_view_machines_in_pool",
        "can_edit_global_entities",
        "can_view_controllers",
        "can_edit_controllers",
        "can_view_identities",
        "can_edit_identities",
        "can_view_configurations",
        "can_edit_configurations",
        "can_edit_notifications",
        "can_view_notifications",
        "can_view_boot_entities",
        "can_edit_boot_entities",
        "can_view_license_keys",
        "can_edit_license_keys",
        "can_view_devices",
        "can_view_ipaddresses",
    ]

    # Methods allowing access to EVERYONE
    ALWAYS_ALLOWED = [
        "can_deploy_machines_in_pool",
        "can_view_available_machines_in_pool",
        "can_view_global_entities",
    ]

    # Methods returning pools ONLY for superusers
    LIST_SUPERUSER_ONLY = [
        "list_pools_with_view_machines_access",
        "list_pools_with_edit_machines_access",
    ]

    # Methods returning pools for EVERYONE
    LIST_ALWAYS_ALLOWED = [
        "list_pools_with_view_available_machines_access",
        "list_pool_with_deploy_machines_access",
    ]

    def __init__(self, *args, **kwargs):
        self.client = None
        self._bind_methods()

    def clear_cache(self):
        # No caching in this mock, so nothing to clear
        pass

    def _bind_methods(self):
        # Permission checks
        for method in self.SUPERUSER_ONLY:
            setattr(self, method, lambda user, *args: user.is_superuser)

        for method in self.ALWAYS_ALLOWED:
            setattr(self, method, lambda user, *args: True)

        # Listing methods
        for method in self.LIST_SUPERUSER_ONLY:
            setattr(
                self,
                method,
                lambda user: self._get_resource_pools()
                if user.is_superuser
                else [],
            )

        for method in self.LIST_ALWAYS_ALLOWED:
            setattr(self, method, lambda user: self._get_resource_pools())

    def _get_resource_pools(self) -> list[int]:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT id FROM maasserver_resourcepool; /* COUNTQUERIES-IGNOREME */"
            )
            return [row[0] for row in cursor.fetchall()]
