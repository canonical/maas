# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from unittest.mock import Mock

import pytest
from sqlalchemy import and_
from sqlalchemy.sql.operators import eq

from maasservicelayer.builders.openfga_tuple import OpenFGATupleBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.openfga_tuples import (
    OpenFGATuplesClauseFactory,
    OpenFGATuplesRepository,
)
from maasservicelayer.db.tables import OpenFGATupleTable
from maasservicelayer.services import OpenFGATupleService, ServiceCollectionV3
from maasservicelayer.services.openfga_tuples import OpenFGAServiceCache
from tests.fixtures.factories.openfga_tuples import create_openfga_tuple
from tests.maasapiserver.fixtures.db import Fixture


@pytest.mark.asyncio
class TestIntegrationOpenFGAService:
    async def test_create(
        self,
        fixture: Fixture,
        services: ServiceCollectionV3,
    ):
        await services.openfga_tuples.create(
            OpenFGATupleBuilder.build_pool("1000")
        )
        retrieved_pool = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.object_id, "1000"),
            ),
        )
        assert len(retrieved_pool) == 1
        assert retrieved_pool[0]["_user"] == "maas:0"
        assert retrieved_pool[0]["object_type"] == "pool"
        assert retrieved_pool[0]["object_id"] == "1000"
        assert retrieved_pool[0]["relation"] == "parent"

    async def test_delete_many(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "2000"
        )
        await services.openfga_tuples.delete_many(
            QuerySpec(where=OpenFGATuplesClauseFactory.with_user("user:1"))
        )
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "2000"),
                eq(OpenFGATupleTable.c._user, "user:1"),
            ),
        )
        assert len(retrieved_tuple) == 0

    async def test_delete_pool(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "maas:0", "user", "parent", "pool", "100"
        )
        await services.openfga_tuples.delete_pool(100)
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "pool"),
                eq(OpenFGATupleTable.c.object_id, "100"),
                eq(OpenFGATupleTable.c._user, "maas:0"),
            ),
        )
        assert len(retrieved_tuple) == 0

    async def test_delete_user(
        self, fixture: Fixture, services: ServiceCollectionV3
    ):
        await create_openfga_tuple(
            fixture, "user:1", "user", "member", "group", "2000"
        )
        await services.openfga_tuples.delete_user(1)
        retrieved_tuple = await fixture.get(
            OpenFGATupleTable.fullname,
            and_(
                eq(OpenFGATupleTable.c.object_type, "group"),
                eq(OpenFGATupleTable.c.object_id, "2000"),
                eq(OpenFGATupleTable.c._user, "user:1"),
            ),
        )
        assert len(retrieved_tuple) == 0


@pytest.mark.asyncio
class TestOpenFGAService:
    async def test_get_client_is_cached(self) -> None:
        cache = OpenFGAServiceCache()
        agents_service = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=Mock(OpenFGATuplesRepository),
            cache=cache,
        )

        agents_service2 = OpenFGATupleService(
            context=Context(),
            openfga_tuple_repository=Mock(OpenFGATuplesRepository),
            cache=cache,
        )

        apiclient = await agents_service.get_client()
        apiclient_again = await agents_service.get_client()

        apiclient2 = await agents_service2.get_client()
        apiclient2_again = await agents_service2.get_client()

        assert (
            id(apiclient)
            == id(apiclient2)
            == id(apiclient_again)
            == id(apiclient2_again)
        )
