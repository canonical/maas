# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.machine_operations import (
    MachineOperationsRepository,
)
from tests.fixtures.factories.node import create_test_machine_entry
from tests.fixtures.factories.operations import create_test_operation_entry
from tests.maasapiserver.fixtures.db import Fixture


class TestMachineOperationsRepository:
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> MachineOperationsRepository:
        return MachineOperationsRepository(Context(connection=db_connection))

    async def test_get_node_id(
        self,
        repository_instance: MachineOperationsRepository,
        fixture: Fixture,
    ) -> None:
        operation = await create_test_operation_entry(fixture, uuid="mo-uuid")
        machine = await create_test_machine_entry(fixture)
        await fixture.create(
            "maasserver_machine_operation",
            [{"operation_uuid": operation.uuid, "node_id": machine["id"]}],
        )
        node_id = await repository_instance.get_node_id(operation.uuid)
        assert node_id == machine["id"]

    async def test_get_node_id_not_found(
        self, repository_instance: MachineOperationsRepository
    ) -> None:
        node_id = await repository_instance.get_node_id("nonexistent-uuid")
        assert node_id is None
