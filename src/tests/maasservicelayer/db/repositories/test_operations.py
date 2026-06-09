# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import uuid as uuid_module

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.operations import OperationsRepository
from maasservicelayer.db.tables import OperationTable
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture

ERROR_MESSAGE = "operation failed"


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
                "created_at": now,
                "updated_at": now,
                "is_bulk": False,
            },
        )
        return operation_uuid

    async def _get_operation(
        self, db_connection: AsyncConnection, operation_uuid: str
    ):
        return (
            await db_connection.execute(
                select(OperationTable).where(
                    OperationTable.c.uuid == operation_uuid
                )
            )
        ).one()

    async def test_update_status_running_sets_started_at(
        self,
        repository: OperationsRepository,
        fixture: Fixture,
        db_connection: AsyncConnection,
    ) -> None:
        operation_uuid = await self._create_operation(fixture)

        await repository.update_status(operation_uuid, OperationStatus.RUNNING)

        operation = await self._get_operation(db_connection, operation_uuid)
        assert operation.status == OperationStatus.RUNNING
        assert operation.started_at is not None
        assert operation.finished_at is None

    async def test_update_status_completed_sets_finished_at(
        self,
        repository: OperationsRepository,
        fixture: Fixture,
        db_connection: AsyncConnection,
    ) -> None:
        operation_uuid = await self._create_operation(fixture)

        await repository.update_status(
            operation_uuid, OperationStatus.COMPLETED
        )

        operation = await self._get_operation(db_connection, operation_uuid)
        assert operation.status == OperationStatus.COMPLETED
        assert operation.finished_at is not None

    async def test_update_status_failed_stores_error(
        self,
        repository: OperationsRepository,
        fixture: Fixture,
        db_connection: AsyncConnection,
    ) -> None:
        operation_uuid = await self._create_operation(fixture)

        await repository.update_status(
            operation_uuid, OperationStatus.FAILED, error=ERROR_MESSAGE
        )

        operation = await self._get_operation(db_connection, operation_uuid)
        assert operation.status == OperationStatus.FAILED
        assert operation.finished_at is not None
        assert operation.result_errors == {"error": ERROR_MESSAGE}

    async def test_update_status_unknown_operation_raises(
        self, repository: OperationsRepository
    ) -> None:
        with pytest.raises(NotFoundException):
            await repository.update_status(
                str(uuid_module.uuid4()), OperationStatus.RUNNING
            )
