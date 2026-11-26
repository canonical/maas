# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from uuid import uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.builders.rackcontrollers import RackControllerBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.rackcontrollers import (
    RackControllersClauseFactory,
    RackControllersRepository,
)
from maasservicelayer.db.tables import NodeTable
from maasservicelayer.models.rackcontrollers import RackController
from tests.fixtures.factories.node import (
    create_test_rack_controller_node_entry,
)
from tests.fixtures.factories.rackcontrollers import (
    create_test_rack_controller_entry,
)
from tests.fixtures.factories.racks import create_test_rack_entry
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestRackControllersClauseFactory:
    def test_with_id(self) -> None:
        clause = RackControllersClauseFactory.with_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_rackcontroller.id = 1"
        )

    def test_with_rack_id(self) -> None:
        clause = RackControllersClauseFactory.with_rack_id(2)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_rackcontroller.rack_id = 2"
        )

    def test_with_rack_id_in(self) -> None:
        clause = RackControllersClauseFactory.with_rack_id_in([1, 2])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_rackcontroller.rack_id IN (1, 2)"
        )

    def test_with_uuid(self) -> None:
        clause = RackControllersClauseFactory.with_uuid("abcde-123456")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_rackcontroller.uuid = 'abcde-123456'"
        )


class TestRackControllersRepository(RepositoryCommonTests[RackController]):
    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> list[RackController]:
        racks = [
            await create_test_rack_entry(fixture, name=f"rack-{i}")
            for i in range(num_objects)
        ]
        nodes = [
            await create_test_rack_controller_node_entry(fixture)
            for _ in range(num_objects)
        ]

        return [
            await create_test_rack_controller_entry(
                fixture,
                uuid=str(uuid4()),
                rack_id=racks[i].id,
                node_id=nodes[i]["id"],
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> RackController:
        rack = await create_test_rack_entry(fixture, name="rack")
        node = await create_test_rack_controller_node_entry(fixture)

        return await create_test_rack_controller_entry(
            fixture,
            uuid=str(uuid4()),
            rack_id=rack.id,
            node_id=node["id"],
        )

    @pytest.fixture
    async def instance_builder(
        self, fixture: Fixture, *args, **kwargs
    ) -> RackControllerBuilder:
        rack = await create_test_rack_entry(fixture, name="builder-rack")
        node = await create_test_rack_controller_node_entry(fixture)

        return RackControllerBuilder(
            uuid=str(uuid4()),
            rack_id=rack.id,
            node_id=node["id"],
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[RackControllerBuilder]:
        return RackControllerBuilder

    @pytest.fixture
    async def repository_instance(
        self, db_connection: AsyncConnection
    ) -> RackControllersRepository:
        return RackControllersRepository(Context(connection=db_connection))

    @pytest.mark.asyncio
    @pytest.mark.allow_transactions
    async def test_delete_node_cascades_to_rack_controllers(
        self, fixture: Fixture, db_connection: AsyncConnection
    ) -> None:
        """Test that deleting a node cascades to delete associated rack controllers."""
        rack = await create_test_rack_entry(fixture, name="test-rack")
        node = await create_test_rack_controller_node_entry(fixture)
        rack_controller = await create_test_rack_controller_entry(
            fixture,
            uuid=str(uuid4()),
            rack_id=rack.id,
            node_id=node["id"],
        )

        # Commit the fixture setup so the deferred FK check below is
        # evaluated against the deletion of the node, instead
        # of being folded into the same transaction as the rack controller insert.
        await db_connection.commit()

        # Verify the rack controller exists
        context = Context(connection=db_connection)
        repo = RackControllersRepository(context)
        found_rack_controller = await repo.get_by_id(rack_controller.id)
        assert found_rack_controller is not None

        stmt = delete(NodeTable).where(NodeTable.c.id == node["id"])
        await db_connection.execute(stmt)
        await db_connection.commit()

        # Verify the rack controller was cascade deleted
        deleted_rack_controller = await repo.get_by_id(rack_controller.id)
        assert deleted_rack_controller is None
