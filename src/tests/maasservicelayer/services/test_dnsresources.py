from unittest.mock import AsyncMock, call, Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import DNSResourceRepository
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestDNSResourcesService:
    async def test_get_one(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_domains_service.get_default_domain = AsyncMock(
            return_value=Domain(
                id=0,
                name="test_domain",
                authoritative=True,
                created=utcnow(),
                updated=utcnow(),
            )
        )

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get = AsyncMock(return_value=None)

        dnsresources_service = DNSResourcesService(
            Mock(AsyncConnection),
            domains_service=mock_domains_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await dnsresources_service.get_one(query=QuerySpec(where=None))

        mock_dnsresource_repository.get_one.assert_called_once_with(
            query=QuerySpec(where=None)
        )

    async def test_release_dynamic_hostname_no_remaining_ips(self) -> None:
        mock_domains_service = Mock(DomainsService)
        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        mock_domains_service.get_default_domain = AsyncMock(
            return_value=domain
        )

        dnsresource = DNSResource(
            id=1,
            name="test_name",
            domain_id=0,
            created=utcnow(),
            updated=utcnow(),
        )

        sip = StaticIPAddress(
            id=1,
            ip="10.0.0.1",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_dnsresources_in_domain_for_ip.return_value = [
            dnsresource
        ]
        mock_dnsresource_repository.get_ips_for_dnsresource.return_value = [
            sip
        ]

        dnsresources_service = DNSResourcesService(
            Mock(AsyncConnection),
            domains_service=mock_domains_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await dnsresources_service.release_dynamic_hostname(sip)

        mock_dnsresource_repository.get_dnsresources_in_domain_for_ip.assert_called_once_with(
            domain, sip
        )

        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                0
            ]
            == ((dnsresource,), {"discovered_only": True, "matching": sip})
        )
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                1
            ]
            == ((dnsresource,), {})
        )

        mock_dnsresource_repository.remove_ip_relation.assert_called_once_with(
            dnsresource, sip
        )

    async def test_update_dynamic_hostname(self) -> None:

        mock_domains_service = Mock(DomainsService)
        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        mock_domains_service.get_default_domain = AsyncMock(
            return_value=domain
        )

        sip = StaticIPAddress(
            id=1,
            ip="10.0.0.1",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=2,
            created=utcnow(),
            updated=utcnow(),
        )
        dnsresource = DNSResource(
            id=1,
            name="test_name",
            domain_id=0,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_one = AsyncMock(
            return_value=dnsresource
        )
        mock_dnsresource_repository.get_dnsresources_in_domain_for_ip.return_value = [
            dnsresource
        ]
        mock_dnsresource_repository.get_ips_for_dnsresource.return_value = []

        dnsresources_service = DNSResourcesService(
            Mock(AsyncConnection),
            domains_service=mock_domains_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await dnsresources_service.update_dynamic_hostname(sip, "test_name")
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                0
            ]
            == call(dnsresource, discovered_only=True, matching=sip)
        )
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                1
            ]
            == call(dnsresource)
        )
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                2
            ]
            == call(dnsresource)
        )
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                3
            ]
            == call(dnsresource, discovered_only=True)
        )
        mock_dnsresource_repository.link_ip.assert_called_once_with(
            dnsresource, sip
        )
