from unittest.mock import call, Mock

import pytest

from maascommon.enums.dns import DnsUpdateAction
from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceRepository,
    DNSResourceResourceBuilder,
)
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestDNSResourcesService:
    async def test_get_one(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_domains_service.get_default_domain.return_value = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_dnsresource_repository = Mock(DNSResourceRepository)
        mock_dnsresource_repository.get.return_value = None

        dnsresources_service = DNSResourcesService(
            Context(),
            domains_service=mock_domains_service,
            dnspublications_service=Mock(DNSPublicationsService),
            dnsresource_repository=mock_dnsresource_repository,
        )

        await dnsresources_service.get_one(query=QuerySpec(where=None))

        mock_dnsresource_repository.get_one.assert_called_once_with(
            query=QuerySpec(where=None)
        )

    async def test_create(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)
        mock_dnsresource_repository = Mock(DNSResourceRepository)

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        dnsresource = DNSResource(
            id=1,
            name="example",
            domain_id=domain.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_domains_service.get_one.return_value = domain
        mock_dnsresource_repository.create.return_value = dnsresource

        service = DNSResourcesService(
            Context(),
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        resource = (
            DNSResourceResourceBuilder()
            .with_name(dnsresource.name)
            .with_domain_id(domain.id)
            .with_created(dnsresource.created)
            .with_updated(dnsresource.updated)
            .build()
        )

        await service.create(resource)

        mock_dnsresource_repository.create.assert_called_once_with(resource)
        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone test_domain added resource example",
            action=DnsUpdateAction.INSERT_NAME,
            label="example",
            rtype="A",
            zone="test_domain",
        )

    async def test_update_change_domain(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)
        mock_dnsresource_repository = Mock(DNSResourceRepository)

        old_domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        new_domain = Domain(
            id=1,
            name="new_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        old_dnsresource = DNSResource(
            id=2,
            name="example",
            domain_id=old_domain.id,
            created=utcnow(),
            updated=utcnow(),
        )
        new_dnsresource = DNSResource(
            id=2,
            name="example",
            domain_id=new_domain.id,
            created=utcnow(),
            updated=utcnow(),
        )
        domain_list = [old_domain, new_domain]

        resource = (
            DNSResourceResourceBuilder()
            .with_name(new_dnsresource.name)
            .with_domain_id(new_domain.id)
            .with_created(new_dnsresource.created)
            .with_updated(new_dnsresource.updated)
            .build()
        )

        mock_domains_service.get_one.side_effect = domain_list
        mock_dnsresource_repository.get_by_id.return_value = old_dnsresource
        mock_dnsresource_repository.update_by_id.return_value = new_dnsresource

        service = DNSResourcesService(
            Context(),
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await service.update_by_id(old_dnsresource.id, resource)

        mock_dnsresource_repository.update_by_id.assert_called_once_with(
            old_dnsresource.id, resource
        )
        mock_dnspublications_service.create_for_config_update.assert_has_calls(
            [
                call(
                    source="zone test_domain removed resource example",
                    action=DnsUpdateAction.DELETE,
                    label=old_dnsresource.name,
                    rtype="A",
                    zone=old_domain.name,
                ),
                call(
                    source="zone new_domain added resource example",
                    action=DnsUpdateAction.INSERT_NAME,
                    label=new_dnsresource.name,
                    rtype="A",
                    zone=new_domain.name,
                ),
            ],
        )

    async def test_update_change_ttl(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)
        mock_dnsresource_repository = Mock(DNSResourceRepository)

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        old_dnsresource = DNSResource(
            id=1,
            name="example",
            domain_id=domain.id,
            created=utcnow(),
            updated=utcnow(),
        )
        dnsresource = DNSResource(
            id=1,
            name="example",
            domain_id=domain.id,
            created=utcnow(),
            updated=utcnow(),
            address_ttl=45,
        )

        resource = (
            DNSResourceResourceBuilder()
            .with_name(dnsresource.name)
            .with_domain_id(domain.id)
            .with_address_ttl(45)
            .with_created(dnsresource.created)
            .with_updated(dnsresource.updated)
            .build()
        )

        mock_domains_service.get_one.return_value = domain
        mock_dnsresource_repository.get_by_id.return_value = old_dnsresource
        mock_dnsresource_repository.update_by_id.return_value = dnsresource

        service = DNSResourcesService(
            Context(),
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await service.update_by_id(old_dnsresource.id, resource)

        mock_dnsresource_repository.update_by_id.assert_called_once_with(
            old_dnsresource.id, resource
        )
        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone test_domain updated resource example",
            action=DnsUpdateAction.UPDATE,
            label=dnsresource.name,
            rtype="A",
            zone=domain.name,
            ttl=45,
        )

    async def test_delete(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)
        mock_dnsresource_repository = Mock(DNSResourceRepository)

        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        dnsresource = DNSResource(
            id=1,
            name="example",
            domain_id=domain.id,
            created=utcnow(),
            updated=utcnow(),
        )

        mock_domains_service.get_one.return_value = domain
        mock_dnsresource_repository.get_by_id.return_value = dnsresource

        service = DNSResourcesService(
            Context(),
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await service.delete_by_id(dnsresource.id)

        mock_dnsresource_repository.delete_by_id.assert_called_once_with(
            id=dnsresource.id
        )
        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone test_domain removed resource example",
            action=DnsUpdateAction.DELETE,
            label=dnsresource.name,
            rtype="A",
            zone=domain.name,
        )

    async def test_release_dynamic_hostname_no_remaining_ips(self) -> None:
        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)
        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        mock_domains_service.get_default_domain.return_value = domain

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
        mock_dnsresource_repository.get_ips_for_dnsresource.side_effect = [
            [sip],
            [],
        ]

        dnsresources_service = DNSResourcesService(
            context=Context(),
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
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
        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone test_domain removed resource test_name",
            action=DnsUpdateAction.DELETE,
            label=dnsresource.name,
            rtype="A",
        )

    async def test_update_dynamic_hostname(self) -> None:

        mock_domains_service = Mock(DomainsService)
        mock_dnspublications_service = Mock(DNSPublicationsService)
        domain = Domain(
            id=0,
            name="test_domain",
            authoritative=True,
            created=utcnow(),
            updated=utcnow(),
        )
        mock_domains_service.get_default_domain.return_value = domain

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
        mock_dnsresource_repository.get_one.return_value = dnsresource
        mock_dnsresource_repository.get_dnsresources_in_domain_for_ip.side_effect = [
            [],
            [dnsresource],
        ]
        mock_dnsresource_repository.get_ips_for_dnsresource.return_value = []

        dnsresources_service = DNSResourcesService(
            context=Context(),
            domains_service=mock_domains_service,
            dnspublications_service=mock_dnspublications_service,
            dnsresource_repository=mock_dnsresource_repository,
        )

        await dnsresources_service.update_dynamic_hostname(sip, "test_name")
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                0
            ]
            == call(dnsresource)
        )
        assert (
            mock_dnsresource_repository.get_ips_for_dnsresource.call_args_list[
                1
            ]
            == call(dnsresource, discovered_only=True)
        )
        mock_dnsresource_repository.link_ip.assert_called_once_with(
            dnsresource, sip
        )
        mock_dnspublications_service.create_for_config_update.assert_called_once_with(
            source="ip 10.0.0.1 linked to resource test_name on zone test_domain",
            action=DnsUpdateAction.INSERT,
            label=dnsresource.name,
            rtype="A",
            ttl=30,
            zone=domain.name,
            answer="10.0.0.1",
        )
