# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.builders.dnspublications import DNSPublicationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnspublications import (
    DNSPublicationRepository,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.dnspublications import DNSPublication
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestDNSPublicationsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return DNSPublicationsService(
            context=Context(),
            dnspublication_repository=Mock(DNSPublicationRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return DNSPublication(id=0, serial=1, source="source", update="update")

    async def test_create_for_config_update_reload(self):
        now = utcnow()

        dnspublication_repository = Mock(DNSPublicationRepository)
        dnspublication_repository.get_latest_serial.return_value = 1

        service = DNSPublicationsService(
            context=Context(),
            dnspublication_repository=dnspublication_repository,
        )

        await service.create_for_config_update(
            source="", action=DnsUpdateAction.RELOAD, timestamp=now
        )

        dnspublication_repository.create.assert_called_once_with(
            builder=DNSPublicationBuilder(
                serial=1,
                source="",
                update=DnsUpdateAction.RELOAD,
                created=now,
            )
        )

    async def test_create_for_config_update_non_reload(self):
        now = utcnow()

        dnspublication_repository = Mock(DNSPublicationRepository)
        dnspublication_repository.get_latest_serial.return_value = 1

        service = DNSPublicationsService(
            context=Context(),
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

        dnspublication_repository.create.assert_called_once_with(
            builder=DNSPublicationBuilder(
                serial=1,
                source="",
                update="INSERT example.com test A 30 1.1.1.1",
                created=now,
            )
        )
