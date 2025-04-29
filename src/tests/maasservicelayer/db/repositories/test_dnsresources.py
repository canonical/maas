# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.dnsresources import DNSResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnsresources import DNSResourceRepository
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.staticipaddress import StaticIPAddress
from tests.fixtures.factories.dnsdata import create_test_dnsdata_entry
from tests.fixtures.factories.dnsresource import create_test_dnsresource_entry
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


@pytest.mark.asyncio
class TestDNSResourceRepository(RepositoryCommonTests[DNSResource]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> DNSResourceRepository:
        return DNSResourceRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[DNSResource]:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresources = [
            await create_test_dnsresource_entry(fixture, domain, sip)
            for _ in range(num_objects)
        ]
        return dnsresources

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> DNSResource:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresource = await create_test_dnsresource_entry(fixture, domain, sip)
        return dnsresource

    @pytest.fixture
    async def instance_builder(self, fixture: Fixture) -> DNSResourceBuilder:
        domain = await create_test_domain_entry(fixture)
        return DNSResourceBuilder(name="test_name", domain_id=domain.id)

    @pytest.fixture
    async def instance_builder_model(self) -> type[DNSResourceBuilder]:
        return DNSResourceBuilder

    @pytest.mark.skip(reason="Not applicable")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        pass

    async def test_get_dnsresources_in_domain_for_ip(
        self, repository_instance: DNSResourceRepository, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresources = [
            await create_test_dnsresource_entry(fixture, domain, sip)
            for _ in range(3)
        ]

        result = await repository_instance.get_dnsresources_in_domain_for_ip(
            domain,
            StaticIPAddress(**sip),
        )

        assert {dnsresource.id for dnsresource in dnsresources} == {
            dnsresource.id for dnsresource in result
        }

    async def test_link_ip(
        self, repository_instance: DNSResourceRepository, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresource = await create_test_dnsresource_entry(fixture, domain)

        ip = StaticIPAddress(**sip)

        await repository_instance.link_ip(dnsresource.id, ip.id)

        link = await repository_instance.get_dnsresources_in_domain_for_ip(
            domain, ip
        )

        assert link[0].id == dnsresource.id

    async def test_get_ips_for_dnsresource(
        self, repository_instance: DNSResourceRepository, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sips = [
            StaticIPAddress(**ip)
            for ip in [
                (
                    await create_test_staticipaddress_entry(
                        fixture, subnet=subnet
                    )
                )[0]
                for _ in range(3)
            ]
        ]
        dnsresource = await create_test_dnsresource_entry(fixture, domain)

        for sip in sips:
            await repository_instance.link_ip(dnsresource.id, sip.id)

        result = await repository_instance.get_ips_for_dnsresource(
            dnsresource.id
        )

        assert {ip.id for ip in sips} == {ip.id for ip in result}

    async def test_remove_ip_relation(
        self, repository_instance: DNSResourceRepository, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresource = await create_test_dnsresource_entry(fixture, domain, sip)

        await repository_instance.remove_ip_relation(
            dnsresource, StaticIPAddress(**sip)
        )

        remaining = await repository_instance.get_ips_for_dnsresource(
            dnsresource.id
        )
        assert len(remaining) == 0

    async def test_get_dnsdata_for_dnsresource(
        self, repository_instance: DNSResourceRepository, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        dnsresource = await create_test_dnsresource_entry(fixture, domain)
        dnsdatas = [
            (await create_test_dnsdata_entry(fixture, dnsresource))
            for _ in range(3)
        ]

        result = await repository_instance.get_dnsdata_for_dnsresource(
            dnsresource.id
        )
        assert result == dnsdatas
