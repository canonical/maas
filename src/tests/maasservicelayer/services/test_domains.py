#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.dns import DomainDNSRecord
from maascommon.enums.dns import DnsUpdateAction
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maasservicelayer.builders.domains import DomainBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.domains import DomainsRepository
from maasservicelayer.exceptions.catalog import (
    BadRequestException,
    ValidationException,
)
from maasservicelayer.exceptions.constants import (
    CANNOT_DELETE_DEFAULT_DOMAIN_VIOLATION_TYPE,
)
from maasservicelayer.models.base import MaasBaseModel
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.users import UsersService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests


@pytest.mark.asyncio
class TestCommonDomainsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return DomainsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=Mock(DNSPublicationsService),
            users_service=Mock(UsersService),
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

    async def test_create(self, service_instance, test_instance):
        # pre_create_hook tested in the next tests
        service_instance.pre_create_hook = AsyncMock()
        return await super().test_create(service_instance, test_instance)

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
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )

        builder = DomainBuilder(
            name=domain.name,
            authoritative=domain.authoritative,
            ttl=domain.ttl,
        )

        await service.create(builder)

        domains_repository.create.assert_called_once_with(builder=builder)
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="added zone example.com",
            action=DnsUpdateAction.RELOAD,
        )

    @pytest.mark.parametrize(
        "name, valid",
        [
            ("domain.com", True),
            ("-b", False),
            ("c-", False),
            ("domain$name", False),
        ],
    )
    async def test_create_invalid_name(self, name: str, valid: bool) -> None:
        domains_repository = Mock(DomainsRepository)
        dnspublications_service = Mock(DNSPublicationsService)
        service = DomainsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )
        if not valid:
            with pytest.raises(ValueError):
                builder = DomainBuilder(name=name)
                await service.create(builder)
        else:
            builder = DomainBuilder(name=name)
            await service.create(builder)

    async def test_create_too_long_name(self) -> None:
        domains_repository = Mock(DomainsRepository)
        dnspublications_service = Mock(DNSPublicationsService)
        service = DomainsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )
        name = "a" * 256
        with pytest.raises(ValidationException):
            builder = DomainBuilder(name=name)
            await service.create(builder)

    async def test_create_duplicate_internaldomain_error(self) -> None:
        domains_repository = Mock(DomainsRepository)
        dnspublications_service = Mock(DNSPublicationsService)
        configurations_service = Mock(ConfigurationsService)
        configurations_service.get.return_value = "maas-internal"
        service = DomainsService(
            context=Context(),
            configurations_service=configurations_service,
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )
        with pytest.raises(ValueError):
            builder = DomainBuilder(name="maas_internal_domain")
            await service.create(builder)

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
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )

        builder = DomainBuilder(
            name=new_domain.name,
            authoritative=new_domain.authoritative,
            ttl=new_domain.ttl,
        )

        await service.update_by_id(old_domain.id, builder)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, builder=builder
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
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )

        builder = DomainBuilder(
            name=new_domain.name,
            authoritative=new_domain.authoritative,
            ttl=new_domain.ttl,
        )

        await service.update_by_id(old_domain.id, builder)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, builder=builder
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
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )

        builder = DomainBuilder(
            name=new_domain.name,
            authoritative=new_domain.authoritative,
            ttl=new_domain.ttl,
        )

        await service.update_by_id(old_domain.id, builder)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, builder=builder
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
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )

        builder = DomainBuilder(
            name=new_domain.name,
            authoritative=new_domain.authoritative,
            ttl=new_domain.ttl,
        )

        await service.update_by_id(old_domain.id, builder)

        domains_repository.update_by_id.assert_called_once_with(
            id=old_domain.id, builder=builder
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
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=dnspublications_service,
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )

        await service.delete_by_id(domain.id)

        domains_repository.delete_by_id.assert_called_once_with(id=domain.id)
        dnspublications_service.create_for_config_update.assert_called_once_with(
            source="removed zone example.com",
            action=DnsUpdateAction.RELOAD,
        )

    async def test_delete_default_domain_error(self) -> None:
        domains_repository = Mock(DomainsRepository)

        domain = Domain(
            id=1,
            name="default_domain",
            authoritative=True,
        )
        domains_repository.get_by_id.return_value = domain
        domains_repository.get_default_domain.return_value = domain
        domains_service = DomainsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=Mock(DNSPublicationsService),
            users_service=Mock(UsersService),
            domains_repository=domains_repository,
        )
        with pytest.raises(BadRequestException) as e:
            await domains_service.delete_by_id(domain.id)
        assert (
            e.value.details[0].type
            == CANNOT_DELETE_DEFAULT_DOMAIN_VIOLATION_TYPE
        )
        domains_repository.delete_by_id.assert_not_called()

    async def test_render_json_for_related_rrdata(self) -> None:
        domains_service = DomainsService(
            context=Context(),
            configurations_service=Mock(ConfigurationsService),
            dnspublications_service=Mock(DNSPublicationsService),
            users_service=Mock(UsersService),
            domains_repository=Mock(DomainsRepository),
        )
        record = DomainDNSRecord(
            name="example.com",
            system_id="abcdef",
            node_type=None,
            user_id=None,
            dnsresource_id=None,
            node_id=1,
            ttl=30,
            rrtype="A",
            rrdata="10.0.0.2",
            dnsdata_id=None,
        )

        domains_service.v3_render_json_for_related_rrdata = AsyncMock(
            side_effect=[[record], {"example.com": [record]}]
        )
        list_result = await domains_service.render_json_for_related_rrdata(
            0, None
        )
        assert isinstance(list_result, list)
        assert list_result == [record.to_dict(with_node_id=False)]

        dict_result = await domains_service.render_json_for_related_rrdata(
            0, None, as_dict=True
        )
        assert isinstance(dict_result, dict)
        assert dict_result == {
            "example.com": [record.to_dict(with_node_id=False)]
        }

    async def test_get_domain_for_node_domain_set(self):
        domain = Domain(id=1, name="test-domain", authoritative=True, ttl=30)
        node = Node(
            id=2,
            system_id="abcdef",
            hostname="test-node",
            domain_id=domain.id,
            status=NodeStatus.READY,
            power_state=PowerState.OFF,
            node_type=NodeTypeEnum.MACHINE,
        )

        domains_repository = Mock(DomainsRepository)
        domains_repository.get_by_id.return_value = domain
        configurations_service = Mock(ConfigurationsService)
        dnspublications_service = Mock(DNSPublicationsService)
        user_service = Mock(UsersService)

        service = DomainsService(
            context=Context(),
            configurations_service=configurations_service,
            dnspublications_service=dnspublications_service,
            users_service=user_service,
            domains_repository=domains_repository,
        )

        result = await service.get_domain_for_node(node)

        assert result.id == domain.id

        domains_repository.get_by_id.assert_called_once_with(domain.id)

    async def test_get_domain_for_node_domain_not_set(self):
        domain = Domain(id=1, name="test-domain", authoritative=True, ttl=30)
        node = Node(
            id=2,
            system_id="abcdef",
            hostname="test-node",
            status=NodeStatus.READY,
            power_state=PowerState.OFF,
            node_type=NodeTypeEnum.MACHINE,
        )

        domains_repository = Mock(DomainsRepository)
        domains_repository.get_default_domain.return_value = domain
        configurations_service = Mock(ConfigurationsService)
        dnspublications_service = Mock(DNSPublicationsService)
        user_service = Mock(UsersService)

        service = DomainsService(
            context=Context(),
            configurations_service=configurations_service,
            dnspublications_service=dnspublications_service,
            users_service=user_service,
            domains_repository=domains_repository,
        )

        result = await service.get_domain_for_node(node)

        assert result.id == domain.id

        domains_repository.get_default_domain.assert_called_once()
