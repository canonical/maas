# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from unittest.mock import AsyncMock, Mock

import pytest

from maascommon.enums.operations import OperationStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.operations import OperationsRepository
from maasservicelayer.services.operations import OperationsService

ERROR_MESSAGE = "operation failed"


@pytest.mark.asyncio
class TestOperationsService:
    async def test_update_status(self) -> None:
        repository = Mock(OperationsRepository)
        repository.update_status = AsyncMock()
        service = OperationsService(
            context=Context(),
            operations_repository=repository,
        )

        await service.update_status(
            operation_uuid="op-uuid",
            status=OperationStatus.FAILED,
            error=ERROR_MESSAGE,
        )

        repository.update_status.assert_called_once_with(
            operation_uuid="op-uuid",
            status=OperationStatus.FAILED,
            error=ERROR_MESSAGE,
        )
