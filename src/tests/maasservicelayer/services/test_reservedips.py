# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import IPv4Address
from unittest.mock import Mock

import pytest

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsRepository,
    ReservedIPsResourceBuilder,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.services.reservedips import ReservedIPsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

TEST_RESERVEDIP = ReservedIP(
    id=1,
    ip=IPv4Address("10.0.0.1"),
    mac_address=MacAddress("01:02:03:04:05:06"),
    comment="test_comment",
    subnet_id=1,
    created=utcnow(),
    updated=utcnow(),
)


@pytest.mark.asyncio
class TestCommonReservedIPsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> ReservedIPsService:
        return ReservedIPsService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            reservedips_repository=Mock(ReservedIPsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> ReservedIP:
        return ReservedIP(
            id=1,
            ip=IPv4Address("10.0.0.0"),
            mac_address=MacAddress("00:00:00:00:00:00"),
            subnet_id=1,
        )

    @pytest.mark.skip(reason="Not implemented yet.")
    async def test_delete_many(self, service_instance, test_instance):
        pass


@pytest.mark.asyncio
class TestReservedIPsService:
    async def test_create(self) -> None:
        reservedips_repository_mock = Mock(ReservedIPsRepository)
        reservedips_repository_mock.create.return_value = TEST_RESERVEDIP
        mock_temporal = Mock(TemporalService)

        reservedips_service = ReservedIPsService(
            context=Context(),
            temporal_service=mock_temporal,
            reservedips_repository=reservedips_repository_mock,
        )

        resource = (
            ReservedIPsResourceBuilder()
            .with_ip(TEST_RESERVEDIP.ip)
            .with_mac_address(TEST_RESERVEDIP.mac_address)
            .with_subnet_id(TEST_RESERVEDIP.subnet_id)
            .with_created(TEST_RESERVEDIP.created)
            .with_updated(TEST_RESERVEDIP.updated)
            .build()
        )

        await reservedips_service.create(resource)

        reservedips_repository_mock.create.assert_called_once_with(
            resource=resource
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(reserved_ip_ids=[TEST_RESERVEDIP.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )

    async def test_delete(self) -> None:
        reservedips_repository_mock = Mock(ReservedIPsRepository)
        reservedips_repository_mock.get_by_id.return_value = TEST_RESERVEDIP
        reservedips_repository_mock.delete_by_id.return_value = TEST_RESERVEDIP
        mock_temporal = Mock(TemporalService)

        reservedips_service = ReservedIPsService(
            context=Context(),
            temporal_service=mock_temporal,
            reservedips_repository=reservedips_repository_mock,
        )

        await reservedips_service.delete_by_id(TEST_RESERVEDIP.id)

        reservedips_repository_mock.delete_by_id.assert_called_once_with(
            id=TEST_RESERVEDIP.id
        )
        mock_temporal.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(reserved_ip_ids=[TEST_RESERVEDIP.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
