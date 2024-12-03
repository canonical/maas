from unittest.mock import Mock

import pytest

from maascommon.enums.dns import DnsUpdateAction
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.domains import (
    DomainResourceBuilder,
    DomainsRepository,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.domains import Domain
from maasservicelayer.services._base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonDomainsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return DomainsService(
            context=Context(),
            dnspublications_service=Mock(DNSPublicationsService),
            domains_repository=Mock(DomainsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        now = utcnow()
        return Domain(
            id=1,
            name="example.com",
            authoritative=True,
            ttl=30,
            created=now,
            updated=now,
        )

    async def test_update_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_update_many(service_instance, test_instance)

    async def test_delete_many(
        self, service_instance, test_instance: MaasBaseModel
    ):
        with pytest.raises(NotImplementedError):
            await super().test_delete_many(service_instance, test_instance)


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
            context=Context(),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainResourceBuilder()
            .with_name(domain.name)
            .with_authoritative(domain.authoritative)
            .with_ttl(domain.ttl)
            .with_created(domain.created)
            .with_updated(domain.updated)
            .build()
        )

        await service.create(resource)

        domains_repository.create.assert_called_once_with(resource=resource)
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

        domains_repository.get_by_id.return_value = old_domain
        domains_repository.update_by_id.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            context=Context(),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update_by_id(old_domain.id, resource)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, resource=resource
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

        domains_repository.get_by_id.return_value = old_domain
        domains_repository.update_by_id.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            context=Context(),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update_by_id(old_domain.id, resource)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, resource=resource
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

        domains_repository.get_by_id.return_value = old_domain
        domains_repository.update_by_id.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            context=Context(),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update_by_id(old_domain.id, resource)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, resource=resource
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

        domains_repository.get_by_id.return_value = old_domain
        domains_repository.update_by_id.return_value = new_domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            context=Context(),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        resource = (
            DomainResourceBuilder()
            .with_name(new_domain.name)
            .with_authoritative(new_domain.authoritative)
            .with_ttl(new_domain.ttl)
            .with_created(new_domain.created)
            .with_updated(new_domain.updated)
            .build()
        )

        await service.update_by_id(old_domain.id, resource)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, resource=resource
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

        domains_repository.get_by_id.return_value = domain
        domains_repository.delete_by_id.return_value = domain

        dnspublications_service = Mock(DNSPublicationsService)

        service = DomainsService(
            context=Context(),
            dnspublications_service=dnspublications_service,
            domains_repository=domains_repository,
        )

        await service.delete_by_id(domain.id)

        domains_repository.delete_by_id.assert_called_once_with(id=domain.id)
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="removed zone example.com",
            action=DnsUpdateAction.RELOAD,
        )
