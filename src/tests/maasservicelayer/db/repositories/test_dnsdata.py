#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.dns import DNSResourceTypeEnum
from maasservicelayer.builders.dnsdata import DNSDataBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.dnsdata import (
    DNSDataClauseFactory,
    DNSDataRepository,
)
from maasservicelayer.db.tables import DNSDataTable
from tests.fixtures.factories.dnsdata import create_test_dnsdata_entry
from tests.fixtures.factories.dnsresource import create_test_dnsresource_entry
from tests.fixtures.factories.domain import create_test_domain_entry
from tests.maasapiserver.fixtures.db import Fixture


class TestDNSDataClauseFactory:
    def test_with_dnsresource_id(self) -> None:
        clause = DNSDataClauseFactory.with_dnsresource_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_dnsdata.dnsresource_id = 1"
        )

    def test_with_rrtype(self) -> None:
        clause = DNSDataClauseFactory.with_rrtype(DNSResourceTypeEnum.CNAME)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_dnsdata.rrtype = 'CNAME'"
        )

    def test_with_rrdata_starting_with(self) -> None:
        clause = DNSDataClauseFactory.with_rrdata_starting_with("0 0 ")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_dnsdata.rrdata LIKE '0 0 ' || '%'"
        )

    def test_with_dnsresource_name(self) -> None:
        clause = DNSDataClauseFactory.with_dnsresource_name("name")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_dnsresource.name = 'name'"
        )

        assert len(clause.joins) == 1
        assert (
            str(
                clause.joins[0].compile(compile_kwargs={"literal_binds": True})
            )
            == "maasserver_dnsresource JOIN maasserver_dnsdata ON maasserver_dnsresource.id = maasserver_dnsdata.dnsresource_id"
        )

    def test_with_domain_id(self) -> None:
        clause = DNSDataClauseFactory.with_domain_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_dnsresource.domain_id = 1"
        )

        assert len(clause.joins) == 1
        assert (
            str(
                clause.joins[0].compile(compile_kwargs={"literal_binds": True})
            )
            == "maasserver_dnsresource JOIN maasserver_dnsdata ON maasserver_dnsresource.id = maasserver_dnsdata.dnsresource_id"
        )


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
