import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
    DNSResourceRepository,
    DNSResourceResourceBuilder,
)
from maasservicelayer.db.tables import DNSResourceTable
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.dnsresource import create_test_dnsresource_entry
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestDNSResourceRepository:
    async def test_get_one(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresource = await create_test_dnsresource_entry(fixture, domain, sip)

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        query = QuerySpec(
            where=DNSResourceClauseFactory.and_clauses(
                [
                    DNSResourceClauseFactory.with_name(dnsresource.name),
                    DNSResourceClauseFactory.with_domain_id(domain.id),
                ]
            ),
        )

        result = await dnsresource_repository.get_one(query)

        assert result.id == dnsresource.id

    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        now = utcnow()

        resource = (
            DNSResourceResourceBuilder()
            .with_name("test_name")
            .with_domain_id(domain.id)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        result = await dnsresource_repository.create(resource)

        assert result is not None
        assert result.name == "test_name"
        assert result.domain_id == domain.id

    async def test_get_dnsresources_in_domain_for_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
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

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        result = (
            await dnsresource_repository.get_dnsresources_in_domain_for_ip(
                domain,
                StaticIPAddress(**sip),
            )
        )

        assert {dnsresource.id for dnsresource in dnsresources} == {
            dnsresource.id for dnsresource in result
        }

    async def test_link_ip(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresource = await create_test_dnsresource_entry(fixture, domain)

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        ip = StaticIPAddress(**sip)

        await dnsresource_repository.link_ip(dnsresource, ip)

        link = await dnsresource_repository.get_dnsresources_in_domain_for_ip(
            domain, ip
        )

        assert link[0].id == dnsresource.id

    async def test_get_ips_for_dnsresource(
        self, db_connection: AsyncConnection, fixture: Fixture
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

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        for sip in sips:
            await dnsresource_repository.link_ip(dnsresource, sip)

        result = await dnsresource_repository.get_ips_for_dnsresource(
            dnsresource
        )

        assert {ip.id for ip in sips} == {ip.id for ip in result}

    async def test_remove_ip_relation(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        subnet = await create_test_subnet_entry(fixture)
        domain = await create_test_domain_entry(fixture)
        sip = (
            await create_test_staticipaddress_entry(fixture, subnet=subnet)
        )[0]
        dnsresource = await create_test_dnsresource_entry(fixture, domain, sip)

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        await dnsresource_repository.remove_ip_relation(
            dnsresource, StaticIPAddress(**sip)
        )

        remaining = await dnsresource_repository.get_ips_for_dnsresource(
            dnsresource
        )
        assert len(remaining) == 0

    async def test_delete(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        dnsresource = await create_test_dnsresource_entry(fixture, domain)

        dnsresource_repository = DNSResourceRepository(
            Context(connection=db_connection)
        )

        await dnsresource_repository.delete_by_id(dnsresource.id)

        stmt = (
            select(DNSResourceTable)
            .select_from(DNSResourceTable)
            .filter(DNSResourceTable.c.id == dnsresource.id)
        )

        result = (await db_connection.execute(stmt)).one_or_none()

        assert result is None
