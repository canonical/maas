#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnsdata import (
    DNSDataRepository,
    DNSDataResourceBuilder,
)
from maasservicelayer.db.tables import DNSDataTable
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.dnsdata import create_test_dnsdata_entry
from tests.fixtures.factories.dnsresource import create_test_dnsresource_entry
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestDNSDataRepository:
    async def test_create(
        self, db_connection: AsyncConnection, fixture: Fixture
    ) -> None:
        domain = await create_test_domain_entry(fixture)
        dnsresource = await create_test_dnsresource_entry(fixture, domain)

        dnsdata_repository = DNSDataRepository(
            Context(connection=db_connection)
        )

        now = utcnow()

        resource = (
            DNSDataResourceBuilder()
            .with_rrtype("TXT")
            .with_rrdata("Hello, World!")
            .with_dnsresource_id(dnsresource.id)
            .with_created(now)
            .with_updated(now)
            .build()
        )

        dnsdata = await dnsdata_repository.create(resource)

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

        resource = (
            DNSDataResourceBuilder().with_rrdata("Hello, World!").build()
        )

        dnsdata = await dnsdata_repository.update_by_id(dnsdata.id, resource)

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