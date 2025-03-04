# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.dns import DnsUpdateAction

# Patch only for 3.6 given that we still have triggers in place that will take care of it.
# from maascommon.workflows.dns import (
#     CONFIGURE_DNS_WORKFLOW_NAME,
#     ConfigureDNSParam,
#     merge_configure_dns_params,
# )
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.dnspublications import (
    DNSPublication,
    DNSPublicationBuilder,
)
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestDNSPublicationsService(ServiceCommonTests):

    @pytest.fixture
    def service_instance(self) -> BaseService:
        return DNSPublicationsService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            dnspublication_repository=Mock(DNSPublicationRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return DNSPublication(id=0, serial=1, source="source", update="update")

    async def test_create_for_config_update_reload(self):
        now = utcnow()

        dnspublication_repository = Mock(DNSPublicationRepository)
        dnspublication_repository.get_latest_serial.return_value = 1

        temporal_service = Mock(TemporalService)

        service = DNSPublicationsService(
            context=Context(),
            temporal_service=temporal_service,
            dnspublication_repository=dnspublication_repository,
        )

        await service.create_for_config_update(
            source="", action=DnsUpdateAction.RELOAD, timestamp=now
        )

        # Patch only for 3.6 given that we still have triggers in place that will take care of it.
        # temporal_service.register_or_update_workflow_call.assert_called_once_with(
        #     CONFIGURE_DNS_WORKFLOW_NAME,
        #     ConfigureDNSParam(need_full_reload=True),
        #     parameter_merge_func=merge_configure_dns_params,
        #     wait=False,
        # )

        dnspublication_repository.create.assert_called_once_with(
            builder=DNSPublicationBuilder(
                serial=2,
                source="",
                update=DnsUpdateAction.RELOAD,
                created=now,
            )
        )

    async def test_create_for_config_update_non_reload(self):
        now = utcnow()

        dnspublication_repository = Mock(DNSPublicationRepository)
        dnspublication_repository.get_latest_serial.return_value = 1

        temporal_service = Mock(TemporalService)

        service = DNSPublicationsService(
            context=Context(),
            temporal_service=temporal_service,
            dnspublication_repository=dnspublication_repository,
        )

        await service.create_for_config_update(
            source="",
            action=DnsUpdateAction.INSERT,
            label="test",
            rtype="A",
            zone="example.com",
            ttl=30,
            answer="1.1.1.1",
            timestamp=now,
        )

        # Patch only for 3.6 given that we still have triggers in place that will take care of it.
        # temporal_service.register_or_update_workflow_call.assert_called_once_with(
        #     CONFIGURE_DNS_WORKFLOW_NAME,
        #     ConfigureDNSParam(need_full_reload=False),
        #     parameter_merge_func=merge_configure_dns_params,
        #     wait=False,
        # )

        dnspublication_repository.create.assert_called_once_with(
            builder=DNSPublicationBuilder(
                serial=2,
                source="",
                update="INSERT example.com test A 30 1.1.1.1",
                created=now,
            )
        )

    async def test_get_publications_since_serial(self):
        dnspublication_repository = Mock(DNSPublicationRepository)

        service = DNSPublicationsService(
            context=Context(),
            temporal_service=Mock(TemporalService),
            dnspublication_repository=dnspublication_repository,
        )

        await service.get_publications_since_serial(1)

        dnspublication_repository.get_publications_since_serial.assert_called_once_with(
            1
        )
