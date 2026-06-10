# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.enums.operations import OperationStatus
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
)
from maasservicelayer.models.operations import Operation
from maasservicelayer.services.operations import OperationsService

ERROR_MESSAGE = "operation failed"


@pytest.mark.asyncio
class TestOperationsService:
    def _service(self, repository: Mock) -> OperationsService:
        return OperationsService(
            context=Context(),
            operations_repository=repository,
        )

    async def test_update_status_running_sets_started(self) -> None:
        repository = Mock(OperationsRepository)
        existing = Mock(Operation)
        existing.id = 1
        repository.get_one = AsyncMock(return_value=existing)
        repository.update_by_id = AsyncMock(return_value=Mock(Operation))
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
        existing = Mock(Operation)
        existing.id = 1
        repository.get_one = AsyncMock(return_value=existing)
        repository.update_by_id = AsyncMock(return_value=Mock(Operation))
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
