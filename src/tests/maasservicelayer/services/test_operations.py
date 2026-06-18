# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import Mock

import pytest

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.builders.operations import OperationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
)
from maasservicelayer.exceptions.catalog import (
    ConflictException,
    NotFoundException,
)
from maasservicelayer.models.base import (
    ListResult,
    MaasBaseModel,
    ResourceBuilder,
)
from maasservicelayer.models.operations import Operation
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.operations import OperationsService
from maasservicelayer.utils.date import utcnow
from tests.maasservicelayer.services.base import ServiceCommonTests

ERROR_MESSAGE = "operation failed"

TEST_OPERATION = Operation(
    id=1,
    uuid="op-uuid",
    op_type=OperationType.MACHINE_DEPLOY,
    status=OperationStatus.ACCEPTED,
    is_bulk=False,
    created=utcnow(),
    updated=utcnow(),
    user_id=1,
)

OTHER_USER_OPERATION = Operation(
    id=2,
    uuid="other-uuid",
    op_type=OperationType.MACHINE_DEPLOY,
    status=OperationStatus.RUNNING,
    is_bulk=False,
    created=utcnow(),
    updated=utcnow(),
    user_id=2,
)


@pytest.mark.asyncio
class TestCommonOperationsService(ServiceCommonTests):
    @pytest.fixture
    def service_instance(self) -> BaseService:
        return OperationsService(
            context=Context(),
            operations_repository=Mock(OperationsRepository),
        )

    @pytest.fixture
    def test_instance(self) -> MaasBaseModel:
        return TEST_OPERATION

    @pytest.fixture
    def builder_model(self) -> type[ResourceBuilder]:
        return OperationBuilder

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_create(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_create(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_create_many(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_create_many(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_many(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_update_many(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_one_not_found(self, service_instance, builder_model):
        await super().test_update_one_not_found(
            service_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_one_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_update_one_etag_match(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_one_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_update_one_etag_not_matching(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_by_id(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_update_by_id(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_by_id_not_found(
        self, service_instance, builder_model
    ):
        await super().test_update_by_id_not_found(
            service_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_by_id_etag_match(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_update_by_id_etag_match(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_update_by_id_etag_not_matching(
        self, service_instance, test_instance, builder_model
    ):
        await super().test_update_by_id_etag_not_matching(
            service_instance, test_instance, builder_model
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_many(self, service_instance, test_instance):
        await super().test_delete_many(service_instance, test_instance)

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_one(self, service_instance, test_instance):
        await super().test_delete_one(service_instance, test_instance)

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_one_not_found(self, service_instance):
        await super().test_delete_one_not_found(service_instance)

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_one_etag_match(
        self, service_instance, test_instance
    ):
        await super().test_delete_one_etag_match(
            service_instance, test_instance
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_one_etag_not_matching(
        self, service_instance, test_instance
    ):
        await super().test_delete_one_etag_not_matching(
            service_instance, test_instance
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_by_id(self, service_instance, test_instance):
        await super().test_delete_by_id(service_instance, test_instance)

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_by_id_not_found(self, service_instance):
        await super().test_delete_by_id_not_found(service_instance)

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_by_id_etag_match(
        self, service_instance, test_instance
    ):
        await super().test_delete_by_id_etag_match(
            service_instance, test_instance
        )

    @pytest.mark.skip(reason="Write functionality deferred to a separate PR")
    async def test_delete_by_id_etag_not_matching(
        self, service_instance, test_instance
    ):
        await super().test_delete_by_id_etag_not_matching(
            service_instance, test_instance
        )


@pytest.mark.asyncio
class TestOperationsService:
    def _service(self, repository: Mock) -> OperationsService:
        return OperationsService(
            context=Context(),
            operations_repository=repository,
        )

    @pytest.fixture
    def operations_repo_mock(self) -> Mock:
        return Mock(OperationsRepository)

    @pytest.fixture
    def operations_service(
        self, operations_repo_mock: Mock
    ) -> OperationsService:
        return OperationsService(
            context=Context(),
            operations_repository=operations_repo_mock,
        )

    async def test_update_status_running_sets_started(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.RUNNING}
        )
        service = self._service(repository)

        await service.update_status("op-uuid", OperationStatus.RUNNING)

        query = repository.get_one.call_args.kwargs["query"]
        assert query == QuerySpec(
            where=OperationsClauseFactory.with_uuid("op-uuid")
        )
        builder = repository.update_by_id.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["status"] == OperationStatus.RUNNING
        assert "started" in populated
        assert "finished" not in populated
        assert "result" not in populated

    async def test_update_status_completed_stores_result(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.COMPLETED}
        )
        service = self._service(repository)

        await service.update_status(
            "op-uuid",
            OperationStatus.COMPLETED,
            result={"deployed": True},
        )

        builder = repository.update_by_id.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["status"] == OperationStatus.COMPLETED
        assert "finished" in populated
        assert populated["result"] == {"deployed": True}
        assert "started" not in populated

    async def test_update_status_failed_stores_error(self) -> None:
        repository = Mock(OperationsRepository)
        repository.get_one.return_value = TEST_OPERATION
        repository.update_by_id.return_value = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.FAILED}
        )
        service = self._service(repository)

        await service.update_status(
            "op-uuid", OperationStatus.FAILED, error=ERROR_MESSAGE
        )

        builder = repository.update_by_id.call_args.kwargs["builder"]
        populated = builder.populated_fields()
        assert populated["status"] == OperationStatus.FAILED
        assert "finished" in populated
        assert "started" not in populated
        assert populated["result"] == {"error": ERROR_MESSAGE}

    async def test_list_for_user_can_view_all(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.list.return_value = ListResult(
            items=[TEST_OPERATION, OTHER_USER_OPERATION], total=2
        )

        result = await operations_service.list_for_user(
            1, 20, user_id=1, can_view_all=True, query=None
        )

        assert result.total == 2
        operations_repo_mock.list.assert_awaited_once_with(
            page=1, size=20, query=None
        )

    async def test_list_for_user_cannot_view_all(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.list.return_value = ListResult(
            items=[TEST_OPERATION], total=1
        )

        result = await operations_service.list_for_user(
            1, 20, user_id=1, can_view_all=False, query=None
        )

        assert result.total == 1
        operations_repo_mock.list.assert_awaited_once()
        call_query = operations_repo_mock.list.call_args.kwargs["query"]
        assert call_query.where == OperationsClauseFactory.with_user_id(1)

    async def test_list_for_user_cannot_view_all_with_filters(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.list.return_value = ListResult(
            items=[TEST_OPERATION], total=1
        )

        filter_query = QuerySpec(
            where=OperationsClauseFactory.with_status(OperationStatus.RUNNING)
        )
        result = await operations_service.list_for_user(
            1, 20, user_id=1, can_view_all=False, query=filter_query
        )

        assert result.total == 1
        operations_repo_mock.list.assert_awaited_once()
        call_query = operations_repo_mock.list.call_args.kwargs["query"]
        assert call_query.where == OperationsClauseFactory.and_clauses(
            [
                OperationsClauseFactory.with_status(OperationStatus.RUNNING),
                OperationsClauseFactory.with_user_id(1),
            ]
        )

    async def test_get_by_uuid_for_user_can_view_all(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.get_by_uuid.return_value = OTHER_USER_OPERATION

        result = await operations_service.get_by_uuid_for_user(
            "other-uuid", user_id=1, can_view_all=True
        )

        assert result == OTHER_USER_OPERATION

    async def test_get_by_uuid_for_user_own_operation(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.get_by_uuid.return_value = TEST_OPERATION

        result = await operations_service.get_by_uuid_for_user(
            "test-uuid", user_id=1, can_view_all=False
        )

        assert result == TEST_OPERATION

    async def test_get_by_uuid_for_user_other_operation_raises_not_found(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.get_by_uuid.return_value = OTHER_USER_OPERATION

        with pytest.raises(NotFoundException):
            await operations_service.get_by_uuid_for_user(
                "other-uuid", user_id=1, can_view_all=False
            )

    async def test_get_by_uuid_for_user_not_found(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.get_by_uuid.return_value = None

        with pytest.raises(NotFoundException):
            await operations_service.get_by_uuid_for_user(
                "nonexistent-uuid", user_id=1, can_view_all=True
            )

    async def test_cancel_for_user_accepted(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operation = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.ACCEPTED}
        )
        operations_repo_mock.get_by_uuid.return_value = operation
        operations_repo_mock.get_one.return_value = operation
        operations_repo_mock.update_by_id.return_value = operation.model_copy(
            update={"status": OperationStatus.CANCELLING}
        )

        result = await operations_service.cancel_for_user(
            uuid="op-uuid", user_id=1, can_edit_all=True
        )

        assert result.status == OperationStatus.CANCELLING

    async def test_cancel_for_user_running(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operation = TEST_OPERATION.model_copy(
            update={"status": OperationStatus.RUNNING}
        )
        operations_repo_mock.get_by_uuid.return_value = operation
        operations_repo_mock.get_one.return_value = operation
        operations_repo_mock.update_by_id.return_value = operation.model_copy(
            update={"status": OperationStatus.CANCELLING}
        )

        result = await operations_service.cancel_for_user(
            uuid="op-uuid", user_id=1, can_edit_all=True
        )

        assert result.status == OperationStatus.CANCELLING

    @pytest.mark.parametrize(
        "status",
        [
            OperationStatus.CANCELLING,
            OperationStatus.CANCELLED,
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
        ],
    )
    async def test_cancel_for_user_raises_conflict_for_terminal_status(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
        status: OperationStatus,
    ) -> None:
        operation = TEST_OPERATION.model_copy(update={"status": status})
        operations_repo_mock.get_by_uuid.return_value = operation

        with pytest.raises(ConflictException):
            await operations_service.cancel_for_user(
                uuid="op-uuid", user_id=1, can_edit_all=True
            )

    async def test_cancel_for_user_not_found(
        self,
        operations_service: OperationsService,
        operations_repo_mock: Mock,
    ) -> None:
        operations_repo_mock.get_by_uuid.return_value = None

        with pytest.raises(NotFoundException):
            await operations_service.cancel_for_user(
                uuid="nonexistent-uuid", user_id=1, can_edit_all=True
            )
