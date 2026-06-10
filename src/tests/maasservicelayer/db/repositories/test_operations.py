# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
import uuid as uuid_module

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.builders.operations import OperationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db._debug import CompiledQuery
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
)
from maasservicelayer.db.tables import OperationTable
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.operations import Operation
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


class TestOperationsClauseFactory:
    def test_with_uuid(self) -> None:
        clause = OperationsClauseFactory.with_uuid("op-uuid")
        stmt = (
            select(OperationTable.c.uuid)
            .select_from(OperationTable)
            .where(clause.condition)
        )
        assert (
            str(CompiledQuery(stmt).sql)
            == "SELECT maasserver_operation.uuid \n"
            "FROM maasserver_operation \n"
            "WHERE maasserver_operation.uuid = :uuid_1"
        )
        assert CompiledQuery(stmt).params == {"uuid_1": "op-uuid"}


class TestOperationsRepository(RepositoryCommonTests[Operation]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> OperationsRepository:
        return OperationsRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[Operation]:
        return [
            await create_test_operation_entry(fixture, uuid=f"test-uuid-{i}")
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def instance_builder(self) -> ResourceBuilder:
        return OperationBuilder(
            uuid="test-uuid-builder",
            op_type=OperationType.MACHINE_DEPLOY,
            status=OperationStatus.ACCEPTED,
            is_bulk=False,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return OperationBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> Operation:
        return await create_test_operation_entry(fixture)

    async def test_update_one_by_uuid(
        self, repository_instance: OperationsRepository, fixture: Fixture
    ) -> None:
        created = await create_test_operation_entry(fixture)
        started = utcnow()

        updated = await repository_instance.update_one(
            query=QuerySpec(
                where=OperationsClauseFactory.with_uuid(created.uuid)
            ),
            builder=OperationBuilder(
                status=OperationStatus.RUNNING, started=started
            ),
        )

        assert updated.status == OperationStatus.RUNNING
        assert updated.started == started
        assert updated.finished is None

    async def test_update_one_unknown_uuid_raises(
        self, repository_instance: OperationsRepository
    ) -> None:
        with pytest.raises(NotFoundException):
            await repository_instance.update_one(
                query=QuerySpec(
                    where=OperationsClauseFactory.with_uuid(
                        str(uuid_module.uuid4())
                    )
                ),
                builder=OperationBuilder(status=OperationStatus.RUNNING),
            )


async def create_test_operation_entry(
    fixture: Fixture,
    *,
    uuid: str = "test-uuid",
    op_type: OperationType = OperationType.MACHINE_DEPLOY,
    status: OperationStatus = OperationStatus.ACCEPTED,
    is_bulk: bool = False,
) -> Operation:
    now = utcnow()
    [row] = await fixture.create(
        "maasserver_operation",
        [
            {
                "uuid": uuid,
                "op_type": op_type.value,
                "status": status.value,
                "is_bulk": is_bulk,
                "created": now,
                "updated": now,
            }
        ],
    )
    return Operation(**row)
