# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maasservicelayer.context import Context
from maasservicelayer.models.configurations import (
    NTPExternalOnlyConfig,
    NTPServersConfig,
    SessionLengthConfig,
    ThemeConfig,
    WindowsKmsHostConfig,
)
from maasservicelayer.services import (
    ConfigurationsService,
    HookedConfigurationsService,
    UsersService,
    VlansService,
)
from maasservicelayer.services.dnsresourcerecordsets import (
    V3DNSResourceRecordSetsService,
)


@pytest.mark.asyncio
class TestHookedConfigurationsService:
    async def test_set(self):
        service = HookedConfigurationsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
            vlans_service=Mock(VlansService),
            v3dnsrrsets_service=Mock(V3DNSResourceRecordSetsService),
        )
        await service.set(ThemeConfig.name, "myvalue")
        service.configurations_service.set.assert_called_once_with(
            name=ThemeConfig.name, value="myvalue", hook_guard=False
        )

    async def test_set_session_length(self):
        service = HookedConfigurationsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
            vlans_service=Mock(VlansService),
            v3dnsrrsets_service=Mock(V3DNSResourceRecordSetsService),
        )
        await service.set(SessionLengthConfig.name, 10000)
        service.configurations_service.set.assert_awaited_once_with(
            name=SessionLengthConfig.name, value=10000, hook_guard=False
        )
        service.users_service.clear_all_sessions.assert_awaited_once()

    async def test_set_ntp_servers(self):
        service = HookedConfigurationsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
            vlans_service=Mock(VlansService),
            v3dnsrrsets_service=Mock(V3DNSResourceRecordSetsService),
        )
        await service.set(NTPServersConfig.name, "ntp.ubuntu.com")
        service.configurations_service.set.assert_awaited_once_with(
            name=NTPServersConfig.name,
            value="ntp.ubuntu.com",
            hook_guard=False,
        )
        service.vlans_service.reconfigure_all_active_dhcp.assert_awaited_once()

    async def test_set_ntp_external_only(self):
        service = HookedConfigurationsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
            vlans_service=Mock(VlansService),
            v3dnsrrsets_service=Mock(V3DNSResourceRecordSetsService),
        )
        await service.set(NTPExternalOnlyConfig.name, False)
        service.configurations_service.set.assert_awaited_once_with(
            name=NTPExternalOnlyConfig.name, value=False, hook_guard=False
        )
        service.vlans_service.reconfigure_all_active_dhcp.assert_awaited_once()

    async def test_set_windows_kms_host(self):
        service = HookedConfigurationsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            users_service=Mock(UsersService),
            vlans_service=Mock(VlansService),
            v3dnsrrsets_service=Mock(V3DNSResourceRecordSetsService),
        )
        await service.set(WindowsKmsHostConfig.name, "foobar.")
        service.configurations_service.set.assert_awaited_once_with(
            name=WindowsKmsHostConfig.name, value="foobar.", hook_guard=False
        )
        service.v3dnsrrsets_service.update_kms_srv.assert_awaited_once_with(
            "foobar."
        )
