from unittest.mock import Mock

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.db.repositories.domains import (
    DomainsRepository,
    DomainsResourceBuilder,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.utils.date import utcnow


@pytest.mark.asyncio
class TestDomainsService:
    async def test_create(self):
        domains_repository = Mock(DomainsRepository)

        now = utcnow()
        domain = Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )

        domains_repository.create.return_value = domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            connection=Mock(AsyncConnection),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainsResourceBuilder()
            .with_name(domain.name)
            .with_authoritative(domain.authoritative)
            .with_ttl(domain.ttl)
            .with_created(domain.created)
            .with_updated(domain.updated)
            .build()
        )

        await service.create(resource)

        domains_repository.create.assert_called_once_with(resource)
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="added zone example.com",
            action=DnsUpdateAction.RELOAD,
        )

    async def test_update_authoritative(self):
        domains_repository = Mock(DomainsRepository)

        now = utcnow()
        old_domain = Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )
        new_domain = Domain(
            id=1,
            name=old_domain.name,
            authoritative=False,
            ttl=old_domain.ttl,
            created=now,
            updated=now,
        )

        domains_repository.get_one.return_value = old_domain
        domains_repository.update.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            connection=Mock(AsyncConnection),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainsResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update(old_domain.id, resource)

        domains_repository.update.assert_called_once_with(
            old_domain.id, resource
        )
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="removed zone example.com",
            action=DnsUpdateAction.RELOAD,
        )

    async def test_update_name(self):
        domains_repository = Mock(DomainsRepository)

        now = utcnow()
        old_domain = Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )
        new_domain = Domain(
            id=1,
            name="example2.com",
            authoritative=True,
            ttl=old_domain.ttl,
            created=now,
            updated=now,
        )

        domains_repository.get_one.return_value = old_domain
        domains_repository.update.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            connection=Mock(AsyncConnection),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainsResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update(old_domain.id, resource)

        domains_repository.update.assert_called_once_with(
            old_domain.id, resource
        )
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone example.com renamed to example2.com",
            action=DnsUpdateAction.RELOAD,
        )

    async def test_update_ttl(self):
        domains_repository = Mock(DomainsRepository)

        now = utcnow()
        old_domain = Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )
        new_domain = Domain(
            id=1,
            name=old_domain.name,
            authoritative=True,
            ttl=31,
            created=now,
            updated=now,
        )

        domains_repository.get_one.return_value = old_domain
        domains_repository.update.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            connection=Mock(AsyncConnection),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainsResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update(old_domain.id, resource)

        domains_repository.update.assert_called_once_with(
            old_domain.id, resource
        )
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone example.com ttl changed to 31",
            action=DnsUpdateAction.RELOAD,
        )

    async def test_update_name_and_ttl(self):
        domains_repository = Mock(DomainsRepository)

        now = utcnow()
        old_domain = Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )
        new_domain = Domain(
            id=1,
            name="example2.com",
            authoritative=True,
            ttl=31,
            created=now,
            updated=now,
        )

        domains_repository.get_one.return_value = old_domain
        domains_repository.update.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            connection=Mock(AsyncConnection),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainsResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update(old_domain.id, resource)

        domains_repository.update.assert_called_once_with(
            old_domain.id, resource
        )
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="zone example.com renamed to example2.com and ttl changed to 31",
            action=DnsUpdateAction.RELOAD,
        )

    async def test_delete(self):
        domains_repository = Mock(DomainsRepository)

        now = utcnow()
        domain = Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )

        domains_repository.get_one.return_value = domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            connection=Mock(AsyncConnection),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        await service.delete(domain.id)

        domains_repository.delete.assert_called_once_with(domain.id)
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="removed zone example.com",
            action=DnsUpdateAction.RELOAD,
        )
