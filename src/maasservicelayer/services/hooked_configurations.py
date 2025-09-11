# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from maasservicelayer.context import Context
from maasservicelayer.models.configurations import (
    NTPExternalOnlyConfig,
    NTPServersConfig,
    SessionLengthConfig,
    WindowsKmsHostConfig,
)
from maasservicelayer.services.base import Service
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dnsresourcerecordsets import (
    V3DNSResourceRecordSetsService,
)
from maasservicelayer.services.users import UsersService
from maasservicelayer.services.vlans import VlansService


class HookedConfigurationsService(Service):
    """
    Service providing unifed access to configuration values, handling hooks for those that need any special handling.
    """

    def __init__(
        self,
        context: Context,
        configurations_service: ConfigurationsService,
        users_service: UsersService,
        vlans_service: VlansService,
        v3dnsrrsets_service: V3DNSResourceRecordSetsService,
    ):
        super().__init__(context)
        self.configurations_service = configurations_service
        self.users_service = users_service
        self.vlans_service = vlans_service
        self.v3dnsrrsets_service = v3dnsrrsets_service

    async def set(self, name: str, value: Any) -> None:
        await self.configurations_service.set(
            name=name, value=value, hook_guard=False
        )

        match name:
            case SessionLengthConfig.name:
                await self.users_service.clear_all_sessions()
            case NTPServersConfig.name:
                await self.vlans_service.reconfigure_all_active_dhcp()
            case NTPExternalOnlyConfig.name:
                await self.vlans_service.reconfigure_all_active_dhcp()
            case WindowsKmsHostConfig.name:
                await self.v3dnsrrsets_service.update_kms_srv(value)
