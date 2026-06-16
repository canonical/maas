# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
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
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.operations import Operation
from maasservicelayer.utils.date import utcnow
from tests.maasapiserver.fixtures.db import Fixture
from tests.maasservicelayer.db.repositories.base import RepositoryCommonTests


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

    def test_with_uuids(self) -> None:
        clause = OperationsClauseFactory.with_uuids(["uuid-1", "uuid-2"])
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.uuid IN ('uuid-1', 'uuid-2')"
        )

    def test_with_status(self) -> None:
        clause = OperationsClauseFactory.with_status(OperationStatus.RUNNING)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.status = 'RUNNING'"
        )

    def test_with_op_type(self) -> None:
        clause = OperationsClauseFactory.with_op_type(
            OperationType.MACHINE_DEPLOY
        )
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.op_type = 'machine.deploy'"
        )

    def test_with_is_bulk(self) -> None:
        clause = OperationsClauseFactory.with_is_bulk(True)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.is_bulk = true"
        )

    def test_with_user_id(self) -> None:
        clause = OperationsClauseFactory.with_user_id(1)
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.user_id = 1"
        )


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

    async def test_get_by_uuid(
        self, repository_instance, created_instance
    ) -> None:
        instance = await repository_instance.get_by_uuid(created_instance.uuid)
        assert instance == created_instance

    async def test_get_by_uuid_not_found(self, repository_instance) -> None:
        instance = await repository_instance.get_by_uuid("non-existent-uuid")
        assert instance is None


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
