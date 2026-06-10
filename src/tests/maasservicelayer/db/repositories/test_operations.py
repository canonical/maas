# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import uuid as uuid_module

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.builders.operations import OperationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.operations import Operation
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture


class TestOperationsClauseFactory:
    def test_with_uuid(self) -> None:
        clause = OperationsClauseFactory.with_uuid("op-uuid")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.uuid = 'op-uuid'"
        )


@pytest.mark.asyncio
class TestOperationsRepository:
    @pytest.fixture
    def repository(
        self, db_connection: AsyncConnection
    ) -> OperationsRepository:
        return OperationsRepository(Context(connection=db_connection))

    async def _create_operation(self, fixture: Fixture) -> str:
        operation_uuid = str(uuid_module.uuid4())
        now = utcnow()
        await fixture.create(
            "maasserver_operation",
            {
                "uuid": operation_uuid,
                "op_type": OperationType.MACHINE_DEPLOY,
                "status": OperationStatus.ACCEPTED,
                "created": now,
                "updated": now,
                "is_bulk": False,
            },
        )
        return operation_uuid

    async def test_update_one_by_uuid(
        self, repository: OperationsRepository, fixture: Fixture
    ) -> None:
        operation_uuid = await self._create_operation(fixture)

        updated = await repository.update_one(
            query=QuerySpec(
                where=OperationsClauseFactory.with_uuid(operation_uuid)
            ),
            builder=OperationBuilder(
                status=OperationStatus.RUNNING, started=utcnow()
            ),
        )

        assert isinstance(updated, Operation)
        assert updated.status == OperationStatus.RUNNING
        assert updated.started is not None
        assert updated.finished is None

    async def test_update_one_unknown_uuid_raises(
        self, repository: OperationsRepository
    ) -> None:
        with pytest.raises(NotFoundException):
            await repository.update_one(
                query=QuerySpec(
                    where=OperationsClauseFactory.with_uuid(
                        str(uuid_module.uuid4())
                    )
                ),
                builder=OperationBuilder(status=OperationStatus.RUNNING),
            )
