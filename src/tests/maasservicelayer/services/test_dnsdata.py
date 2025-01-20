#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnsdata import DNSDataRepository
from maasservicelayer.models.dnsdata import DNSData, DNSDataBuilder
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.services.dnsdata import DNSDataService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestDNSData:
    async def test_create(self) -> None:
        mock_dnsdata_repository = Mock(DNSDataRepository)
        mock_dnsresources_service = Mock(DNSResourcesService)
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)

        now = utcnow()

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=now,
            updated=now,
        )
        dnsresource = DNSResource(
            id=1,
            name="test_resource",
            domain_id=domain.id,
            created=now,
            updated=now,
        )
        dnsdata = DNSData(
            id=2,
            dnsresource_id=dnsresource.id,
            rrtype="TXT",
            rrdata="Hello, World!",
        )

        mock_domains_service.get_by_id.return_value = domain
        mock_dnsresources_service.get_by_id.return_value = dnsresource
        mock_dnsdata_repository.create.return_value = dnsdata

        service = DNSDataService(
            context=Context(),
            dnsresources_service=mock_dnsresources_service,
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsdata_repository=mock_dnsdata_repository,
        )

        builder = DNSDataBuilder(
            dnsresource_id=dnsdata.dnsresource_id,
            rrtype=dnsdata.rrtype,
            rrdata=dnsdata.rrdata,
        )

        await service.create(builder)

        mock_dnsdata_repository.create.assert_called_once_with(builder=builder)

        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="added TXT to resource test_resource on zone test_domain",
            action=DnsUpdateAction.INSERT,
            label="test_resource",
            rtype="TXT",
            zone="test_domain",
            ttl=30,
            answer="Hello, World!",
        )

    async def test_update_by_id(self) -> None:
        mock_dnsdata_repository = Mock(DNSDataRepository)
        mock_dnsresources_service = Mock(DNSResourcesService)
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)

        now = utcnow()

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=now,
            updated=now,
        )
        dnsresource = DNSResource(
            id=1,
            name="test_resource",
            domain_id=domain.id,
            created=now,
            updated=now,
        )
        dnsdata = DNSData(
            id=2,
            dnsresource_id=dnsresource.id,
            rrtype="TXT",
            rrdata="Hello, World!",
        )

        mock_domains_service.get_by_id.return_value = domain
        mock_dnsresources_service.get_by_id.return_value = dnsresource
        mock_dnsdata_repository.get_by_id.return_value = dnsdata
        mock_dnsdata_repository.update_by_id.return_value = dnsdata

        service = DNSDataService(
            context=Context(),
            dnsresources_service=mock_dnsresources_service,
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsdata_repository=mock_dnsdata_repository,
        )

        builder = DNSDataBuilder(
            dnsresource_id=dnsdata.dnsresource_id,
            rrtype=dnsdata.rrtype,
            rrdata=dnsdata.rrdata,
        )

        await service.update_by_id(dnsdata.id, builder)

        mock_dnsdata_repository.update_by_id.assert_called_once_with(
            id=dnsdata.id, builder=builder
        )

        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="updated TXT in resource test_resource on zone test_domain",
            action=DnsUpdateAction.UPDATE,
            label="test_resource",
            zone="test_domain",
            rtype="TXT",
            ttl=30,
            answer="Hello, World!",
        )

    async def test_delete_by_id(self) -> None:
        mock_dnsdata_repository = Mock(DNSDataRepository)
        mock_dnsresources_service = Mock(DNSResourcesService)
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)

        now = utcnow()

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=now,
            updated=now,
        )
        dnsresource = DNSResource(
            id=1,
            name="test_resource",
            domain_id=domain.id,
            created=now,
            updated=now,
        )
        dnsdata = DNSData(
            id=2,
            dnsresource_id=dnsresource.id,
            rrtype="TXT",
            rrdata="Hello, World!",
        )

        mock_domains_service.get_by_id.return_value = domain
        mock_dnsresources_service.get_by_id.return_value = dnsresource
        mock_dnsdata_repository.get_by_id.return_value = dnsdata
        mock_dnsdata_repository.delete_by_id.return_value = dnsdata

        service = DNSDataService(
            context=Context(),
            dnsresources_service=mock_dnsresources_service,
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsdata_repository=mock_dnsdata_repository,
        )

        await service.delete_by_id(dnsdata.id)

        mock_dnsdata_repository.delete_by_id.assert_called_once_with(
            id=dnsdata.id
        )
        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="removed TXT from resource test_resource on zone test_domain",
            action=DnsUpdateAction.DELETE,
            label=dnsresource.name,
            zone=domain.name,
            rtype=dnsdata.rrtype,
            ttl=30,
            answer=dnsdata.rrdata,
        )
