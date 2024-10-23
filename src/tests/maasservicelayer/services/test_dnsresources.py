from datetime import datetime
from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.db.repositories.dnsresources import DNSResourceRepository
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService


@pytest.mark.asyncio
class TestDNSResourcesService:
    def _create_service(
        self,
        db_connection: AsyncConnection,
        dnsresource_repo: DNSResourceRepository | None = None,
        domains_repo: DomainsRepository | None = None,
    ) -> DNSResourcesService:
        return DNSResourcesService(
            db_connection,
            DomainsService(
                db_connection,
                domains_repository=domains_repo,
            ),
            dnsresource_repository=dnsresource_repo,
        )

    async def test_get_or_create_create(
        self, db_connection: AsyncConnection
    ) -> None:
        mock_domains_repository = Mock(DomainsRepository)

        async def mock_get_default_domain():
            return Domain(
                id=0,
                name="test_domain",
                authoritative=True,
                created=datetime.utcnow(),
                updated=datetime.utcnow(),
            )

        mock_domains_repository.get_default_domain = mock_get_default_domain

        mock_dnsresource_repository = Mock(DNSResourceRepository)

        async def mock_get(_):
            return None

        mock_dnsresource_repository.get = mock_get

        dnsresources_service = self._create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repository,
            domains_repo=mock_domains_repository,
        )

        await dnsresources_service.get_or_create(
            name="test_name",
        )

        assert (
            mock_dnsresource_repository.create.call_args[0][0]["name"]
            == "test_name"
        )
        assert (
            mock_dnsresource_repository.create.call_args[0][0]["domain_id"]
            == 0
        )

    async def test_get_or_create_get(
        self, db_connection: AsyncConnection
    ) -> None:
        mock_dnsresource_repository = Mock(DNSResourceRepository)

        async def mock_get(_):
            return DNSResource(
                id=1,
                name="test_name",
                domain_id=0,
                created=datetime.utcnow(),
                updated=datetime.utcnow(),
            )

        mock_dnsresource_repository.get = mock_get

        dnsresources_service = self._create_service(
            db_connection, mock_dnsresource_repository
        )

        result, created = await dnsresources_service.get_or_create(
            name="test_name", domain_id=0
        )

        assert result is not None
        assert 1 == result.id
        assert created is False

    async def test_release_dynamic_hostname_no_remaining_ips(
        self, db_connection: AsyncConnection
    ) -> None:
        mock_domains_repository = Mock(DomainsRepository)

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        async def mock_get_default_domain():
            return domain

        dnsresource = DNSResource(
            id=1,
            name="test_name",
            domain_id=0,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        sip = StaticIPAddress(
            id=1,
            ip="10.0.0.1",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=2,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        mock_domains_repository.get_default_domain = mock_get_default_domain

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get_dnsresources_in_domain_for_ip.return_value = [
            dnsresource
        ]
        mock_dnsresource_repository.get_ips_for_dnsresource.return_value = [
            sip
        ]

        dnsresources_service = self._create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repository,
            domains_repo=mock_domains_repository,
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

    async def test_update_dynamic_hostname(
        self, db_connection: AsyncConnection
    ) -> None:
        sip = StaticIPAddress(
            id=1,
            ip="10.0.0.1",
            alloc_type=IpAddressType.DISCOVERED,
            lease_time=600,
            subnet_id=2,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )
        dnsresource = DNSResource(
            id=1,
            name="test_name",
            domain_id=0,
            created=datetime.utcnow(),
            updated=datetime.utcnow(),
        )

        mock_domains_repository = Mock(DomainsRepository)

        async def mock_get_default_domain():
            return Domain(
                id=0,
                name="test_domain",
                authoritative=True,
                created=datetime.utcnow(),
                updated=datetime.utcnow(),
            )

        mock_domains_repository.get_default_domain = mock_get_default_domain

        mock_dnsresource_repository = Mock(DNSResourceRepository)

        async def mock_get(_):
            return dnsresource

        mock_dnsresource_repository.get = mock_get
        mock_dnsresource_repository.get_ips_for_dnsresource.return_value = []

        dnsresources_service = self._create_service(
            db_connection,
            dnsresource_repo=mock_dnsresource_repository,
            domains_repo=mock_domains_repository,
        )

        await dnsresources_service.update_dynamic_hostname(sip, "test_name")

        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                0
            ]
            == ((dnsresource,), {})
        )
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                1
            ]
            == ((dnsresource,), {"dynamic_only": True})
        )
        mock_dnsresource_repository.link_ip.assert_called_once_with(
            dnsresource, sip
        )
