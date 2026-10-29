# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machines_v2 import MachinesV2Repository
from maasservicelayer.filters.nodes import NodeFilters
from maasservicelayer.filters.query import OrderBy, QuerySpec
from maasservicelayer.models.nodes import Node
from tests.fixtures.factories.node import create_test_machine_entry
from tests.maasapiserver.fixtures.db import Fixture


async def test_machine_projection_filters_and_orders_actual_rows(
    db_connection: AsyncConnection, fixture: Fixture
) -> None:
    first = await create_test_machine_entry(fixture, hostname="alpha")
    second = await create_test_machine_entry(fixture, hostname="bravo")
    await create_test_machine_entry(fixture, hostname="charlie")
    repository = MachinesV2Repository(Context(connection=db_connection))

    rows = await repository.get_many(
        QuerySpec(
            where=NodeFilters.with_ids([first["id"], second["id"]]),
            order_by=(OrderBy(Node, "hostname", descending=True),),
        )
    )

    assert [
        (row["id"], row["hostname"], row["system_id"]) for row in rows
    ] == [
        (second["id"], "bravo", second["system_id"]),
        (first["id"], "alpha", first["system_id"]),
    ]
