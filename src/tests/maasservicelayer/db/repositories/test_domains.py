#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
from datetime import datetime, timezone
import random
from typing import TypeVar

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import IpAddressType
from maasservicelayer.builders.domains import DomainBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.domains import (
    DomainsClauseFactory,
    DomainsRepository,
)
from maasservicelayer.models.base import MaasTimestampedBaseModel
from maasservicelayer.models.domains import Domain
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.fixtures.factories.forwarddnsserver import (
    create_test_forwarddnsserver_entry,
)
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests

T = TypeVar("T", bound=MaasTimestampedBaseModel)


class TestDomainsClauseFactory:
    def test_with_id(self) -> None:
        clause = DomainsClauseFactory.with_id(1)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_domain.id = 1")

    def test_with_name(self) -> None:
        clause = DomainsClauseFactory.with_name("name")
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_domain.name = 'name'")

    def test_with_authoritative(self) -> None:
        clause = DomainsClauseFactory.with_authoritative(True)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_domain.authoritative = true")

    def test_with_ttl(self) -> None:
        clause = DomainsClauseFactory.with_ttl(30)
        assert str(
            clause.condition.compile(compile_kwargs={"literal_binds": True})
        ) == ("maasserver_domain.ttl = 30")


@pytest.mark.asyncio
class TestDomainsRepository(RepositoryCommonTests[Domain]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> DomainsRepository:
        return DomainsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[Domain]:
        # The default domain is created by the migrations
        # and it has the following timestamp hardcoded in the test sql dump,
        # see src/maasserver/testing/inital.maas_test.sql:12260
        ts = datetime(2021, 11, 19, 12, 40, 45, 172211, tzinfo=timezone.utc)
        created_domains = [
            Domain(
                id=0,
                created=ts,
                updated=ts,
                name="maas",
                authoritative=True,
                ttl=None,
            )
        ]
        created_domains.extend(
            [
                await create_test_domain_entry(
                    fixture,
                )
                for _ in range(num_objects - 1)
            ]
        )
        return created_domains

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Domain:
        return await create_test_domain_entry(fixture)

    @pytest.fixture
    async def instance_builder_model(self) -> type[DomainBuilder]:
        return DomainBuilder

    @pytest.fixture
    async def instance_builder(self, fixture: Fixture) -> DomainBuilder:
        return DomainBuilder(name="my_domain", authoritative=True)

    async def test_get_default_domain(
        self, repository_instance: DomainsRepository
    ) -> None:
        # default domain is created by the migrations
        default_domain = await repository_instance.get_default_domain()
        assert default_domain is not None
        assert default_domain.id == 0
        assert default_domain.name == "maas"

    async def test_user_reserved_addresses_have_default_hostnames(
        self, repository_instance: DomainsRepository, fixture: Fixture
    ):
        # Moved from src/maasserver/models/tests/test_staticipaddress.py
        # Reserved IPs get default hostnames when none are given.
        subnet = await create_test_subnet_entry(fixture)
        num_ips = random.randint(3, 5)
        ips = [
            await create_test_staticipaddress_entry(
                fixture,
                subnet=subnet,
                alloc_type=IpAddressType.USER_RESERVED.value,
            )
            for _ in range(num_ips)
        ]
        mappings = await repository_instance._get_special_mappings(
            default_ttl=30
        )
        assert len(mappings) == len(ips)

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    async def test_get_forwarded_domains(
        self, repository_instance: DomainsRepository, fixture: Fixture
    ) -> None:
        domains = [
            await create_test_domain_entry(
                fixture, name=f"test-domain-{i}", authoritative=False
            )
            for i in range(3)
        ]
        fwd_srvrs = [
            await create_test_forwarddnsserver_entry(
                fixture, ip_address=f"10.0.0.{i + 1}", domain=domain
            )
            for i, domain in enumerate(domains)
        ]

        fwd_domains = await repository_instance.get_forwarded_domains()

        assert len(fwd_domains) == len(domains)

        for fwd_domain, fwd_srvr in fwd_domains:
            assert fwd_domain in domains
            assert fwd_srvr in fwd_srvrs
