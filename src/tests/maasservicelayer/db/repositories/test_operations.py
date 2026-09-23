# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from collections.abc import Sequence
import uuid as uuid_module

import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlalchemy.sql.operators import eq

from maascommon.enums.operations import (
    OperationStatus,
    OperationTaskStatus,
    OperationType,
)
from maasservicelayer.builders.operations import (
    OperationBuilder,
    OperationTaskBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import Clause, QuerySpec
from maasservicelayer.db.repositories.base import MultipleResultsException
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
    OperationTasksRepository,
)
from maasservicelayer.exceptions.catalog import NotFoundException
from maasservicelayer.models.base import ResourceBuilder
from maasservicelayer.models.operations import Operation, OperationTask
from maasservicelayer.utils.date import utcnow
from tests.fixtures.factories.operations import (
    create_test_operation_entry,
    create_test_operation_task_entry,
)
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

    def test_with_parent_id(self) -> None:
        clause = OperationsClauseFactory.with_parent_id("parent-uuid")
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.parent_id = 'parent-uuid'"
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

    def test_without_parent_id(self) -> None:
        clause = OperationsClauseFactory.without_parent_id()
        assert (
            str(
                clause.condition.compile(
                    compile_kwargs={"literal_binds": True}
                )
            )
            == "maasserver_operation.parent_id IS NULL"
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


class TestOperationTasksRepository(RepositoryCommonTests[OperationTask]):
    @pytest.fixture
    def repository_instance(
        self, db_connection: AsyncConnection
    ) -> OperationTasksRepository:
        return OperationTasksRepository(Context(connection=db_connection))

    @pytest.fixture
    async def _setup_test_list(
        self, fixture: Fixture, num_objects: int
    ) -> Sequence[OperationTask]:
        operation = await create_test_operation_entry(
            fixture, uuid="task-list-op"
        )
        return [
            await create_test_operation_task_entry(
                fixture, operation_uuid=operation.uuid, task_number=i
            )
            for i in range(num_objects)
        ]

    @pytest.fixture
    async def instance_builder(self, fixture: Fixture) -> OperationTaskBuilder:
        operation = await create_test_operation_entry(
            fixture, uuid="task-builder-op"
        )
        return OperationTaskBuilder(
            operation_uuid=operation.uuid,
            name="task1",
            task_number=1,
            status=OperationTaskStatus.RUNNING,
        )

    @pytest.fixture
    async def instance_builder_model(self) -> type[ResourceBuilder]:
        return OperationTaskBuilder

    @pytest.fixture
    async def created_instance(self, fixture: Fixture) -> OperationTask:
        operation = await create_test_operation_entry(
            fixture, uuid="task-created-op"
        )
        return await create_test_operation_task_entry(
            fixture, operation_uuid=operation.uuid
        )

    @pytest.mark.skip(reason="Operation tasks have no uniqueness constraint")
    async def test_create_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    @pytest.mark.skip(reason="Operation tasks have no uniqueness constraint")
    async def test_create_many_duplicated(
        self, repository_instance, instance_builder
    ):
        raise NotImplementedError()

    async def test_update_by_id(
        self,
        repository_instance: OperationTasksRepository,
        instance_builder: OperationTaskBuilder,
    ) -> None:
        created = await repository_instance.create(instance_builder)
        updated = await repository_instance.update_by_id(
            created.id,
            OperationTaskBuilder(status=OperationTaskStatus.COMPLETED),
        )
        assert updated.status == OperationTaskStatus.COMPLETED

    async def test_update_one(
        self,
        repository_instance: OperationTasksRepository,
        instance_builder: OperationTaskBuilder,
    ) -> None:
        created = await repository_instance.create(instance_builder)
        updated = await repository_instance.update_one(
            QuerySpec(
                where=Clause(
                    eq(
                        repository_instance.get_repository_table().c.id,
                        created.id,
                    )
                )
            ),
            OperationTaskBuilder(status=OperationTaskStatus.COMPLETED),
        )
        assert updated.status == OperationTaskStatus.COMPLETED

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_one_multiple_results(
        self,
        repository_instance: OperationTasksRepository,
        _setup_test_list: Sequence[OperationTask],
        num_objects: int,
    ) -> None:
        with pytest.raises(MultipleResultsException):
            await repository_instance.update_one(
                QuerySpec(),
                OperationTaskBuilder(status=OperationTaskStatus.COMPLETED),
            )

    @pytest.mark.parametrize("num_objects", [2])
    async def test_update_many(
        self,
        repository_instance: OperationTasksRepository,
        _setup_test_list: Sequence[OperationTask],
        num_objects: int,
    ) -> None:
        updated = await repository_instance.update_many(
            QuerySpec(),
            OperationTaskBuilder(status=OperationTaskStatus.COMPLETED),
        )
        assert len(updated) == 2
        assert all(
            task.status == OperationTaskStatus.COMPLETED for task in updated
        )
