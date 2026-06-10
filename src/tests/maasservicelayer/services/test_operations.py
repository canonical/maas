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
from maasservicelayer.models.base import MaasBaseModel, ResourceBuilder
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


@pytest.mark.asyncio
class TestOperationsService:
    def _service(self, repository: Mock) -> OperationsService:
        return OperationsService(
            context=Context(),
            operations_repository=repository,
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
        assert "result_errors" not in populated

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
        assert populated["result_errors"] == {"error": ERROR_MESSAGE}
