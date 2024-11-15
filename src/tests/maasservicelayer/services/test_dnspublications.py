from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.dns import DnsUpdateAction
from maascommon.workflows.dns import (
    CONFIGURE_DNS_WORKFLOW_NAME,
    ConfigureDNSParam,
    merge_configure_dns_params,
)
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
    DNSPublicationResourceBuilder,
)
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.temporal import TemporalService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestDNSPublicationsService:
    async def test_create(self):
        now = utcnow()
        resource = (
            DNSPublicationResourceBuilder()
            .with_serial(1)
            .with_source("")
            .with_update("")
            .with_created(now)
            .with_updated(now)
            .build()
        )

        dnspublication_repository = Mock(DNSPublicationRepository)

        service = DNSPublicationsService(
            connection=Mock(AsyncConnection),
            temporal_service=Mock(TemporalService),
            dnspublication_repository=dnspublication_repository,
        )

        await service.create(resource)

        dnspublication_repository.create.assert_called_once_with(resource)

    async def test_create_for_config_update_reload(self):
        now = utcnow()

        dnspublication_repository = Mock(DNSPublicationRepository)
        dnspublication_repository.get_latest_serial.return_value = 1

        temporal_service = Mock(TemporalService)

        service = DNSPublicationsService(
            connection=Mock(AsyncConnection),
            temporal_service=temporal_service,
            dnspublication_repository=dnspublication_repository,
        )

        await service.create_for_config_update(
            source="", action=DnsUpdateAction.RELOAD, timestamp=now
        )

        temporal_service.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DNS_WORKFLOW_NAME,
            ConfigureDNSParam(need_full_reload=True),
            parameter_merge_func=merge_configure_dns_params,
            wait=False,
        )

        dnspublication_repository.create.assert_called_once_with(
            DNSPublicationResourceBuilder()
            .with_serial(2)
            .with_source("")
            .with_update(DnsUpdateAction.RELOAD)
            .with_created(now)
            .with_updated(now)
            .build()
        )

    async def test_create_for_config_update_non_reload(self):
        now = utcnow()

        dnspublication_repository = Mock(DNSPublicationRepository)
        dnspublication_repository.get_latest_serial.return_value = 1

        temporal_service = Mock(TemporalService)

        service = DNSPublicationsService(
            connection=Mock(AsyncConnection),
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

        temporal_service.register_or_update_workflow_call.assert_called_once_with(
            CONFIGURE_DNS_WORKFLOW_NAME,
            ConfigureDNSParam(need_full_reload=False),
            parameter_merge_func=merge_configure_dns_params,
            wait=False,
        )

        dnspublication_repository.create.assert_called_once_with(
            DNSPublicationResourceBuilder()
            .with_serial(2)
            .with_source("")
            .with_update("INSERT example.com test A 30 1.1.1.1")
            .with_created(now)
            .with_updated(now)
            .build()
        )

    async def test_get_publications_since_serial(self):
        dnspublication_repository = Mock(DNSPublicationRepository)

        service = DNSPublicationsService(
            connection=Mock(AsyncConnection),
            temporal_service=Mock(TemporalService),
            dnspublication_repository=dnspublication_repository,
        )

        await service.get_publications_since_serial(1)

        dnspublication_repository.get_publications_since_serial.assert_called_once_with(
            1
        )
