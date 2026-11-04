#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.builders.dnsdata import DNSDataBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnsdata import DNSDataRepository
from maasservicelayer.db.tables import DNSDataTable
from maasservicelayer.filters.dnsdata import DNSDataFilters
from maasservicelayer.filters.query import QuerySpec
from tests.fixtures.factories.dnsdata import create_test_dnsdata_entry
from tests.fixtures.factories.dnsresource import create_test_dnsresource_entry
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestDNSDataRepository:
    @pytest.mark.parametrize(
        "filter_name, value",
        [
            ("with_rrtype", DNSResourceTypeEnum.TXT),
            ("with_rrdata_starting_with", "matching "),
            ("with_dnsresource_name", "matching"),
            ("with_domain_id", None),
            ("with_dnsresource_id", None),
        ],
    )
    async def test_get_many_with_domain_filters(
        self,
        db_connection: AsyncConnection,
        fixture: Fixture,
        filter_name: str,
        value,
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        resource = await create_test_dnsresource_entry(
            fixture, domain, name="matching"
        )
        expected = await create_test_dnsdata_entry(
            fixture, resource, rrtype="TXT", rrdata="matching record"
        )
        other_domain = await create_test_domain_entry(fixture)
        other_resource = await create_test_dnsresource_entry(
            fixture, other_domain, name="other"
        )
        await create_test_dnsdata_entry(
            fixture, other_resource, rrtype="CNAME", rrdata="other record"
        )
        if filter_name == "with_domain_id":
            value = domain.id
        elif filter_name == "with_dnsresource_id":
            value = resource.id
        repository = DNSDataRepository(Context(connection=db_connection))

        result = await repository.get_many(
            QuerySpec(where=getattr(DNSDataFilters, filter_name)(value))
        )

        assert result == [expected]

    async def test_combines_related_resource_filters(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        resource = await create_test_dnsresource_entry(
            fixture, domain, name="matching"
        )
        expected = await create_test_dnsdata_entry(fixture, resource)
        other_resource = await create_test_dnsresource_entry(
            fixture, domain, name="other"
        )
        await create_test_dnsdata_entry(fixture, other_resource)
        other_domain = await create_test_domain_entry(fixture)
        same_name_resource = await create_test_dnsresource_entry(
            fixture, other_domain, name="matching"
        )
        await create_test_dnsdata_entry(fixture, same_name_resource)
        repository = DNSDataRepository(Context(connection=db_connection))

        result = await repository.get_many(
            QuerySpec(
                where=DNSDataFilters.and_filters(
                    [
                        DNSDataFilters.with_domain_id(domain.id),
                        DNSDataFilters.with_dnsresource_name("matching"),
                    ]
                )
            )
        )

        assert result == [expected]

    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        dnsresource = await create_test_dnsresource_entry(fixture, domain)

        dnsdata_repository = DNSDataRepository(
            Context(connection=db_connection)
        )

        builder = DNSDataBuilder(
            rrtype="TXT", rrdata="Hello, World!", dnsresource_id=dnsresource.id
        )

        dnsdata = await dnsdata_repository.create(builder)

        assert dnsdata.rrtype == "TXT"
        assert dnsdata.rrdata == "Hello, World!"
        assert dnsdata.dnsresource_id == dnsresource.id

    async def test_update_by_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        dnsresource = await create_test_dnsresource_entry(fixture, domain)
        dnsdata = await create_test_dnsdata_entry(fixture, dnsresource)

        assert dnsdata.rrdata == ""

        dnsdata_repository = DNSDataRepository(
            Context(connection=db_connection)
        )

        builder = DNSDataBuilder(rrdata="Hello, World!")

        dnsdata = await dnsdata_repository.update_by_id(dnsdata.id, builder)

        assert dnsdata.rrdata == "Hello, World!"

    async def test_delete_by_id(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        dnsresource = await create_test_dnsresource_entry(fixture, domain)
        dnsdata = await create_test_dnsdata_entry(fixture, dnsresource)

        dnsdata_repository = DNSDataRepository(
            Context(connection=db_connection)
        )

        await dnsdata_repository.delete_by_id(dnsdata.id)

        stmt = (
            select(DNSDataTable)
            .select_from(DNSDataTable)
            .where(DNSDataTable.c.id == dnsdata.id)
        )

        result = (await db_connection.execute(stmt)).one_or_none()

        assert result is None
