# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.operations import OperationStatus
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.operations import OperationsRepository
from maasservicelayer.services.base import Service


class OperationsService(Service):
    """Service for managing long-running operations."""

    def __init__(
        self,
        context: Context,
        operations_repository: OperationsRepository,
    ):
        super().__init__(context)
        self.operations_repository = operations_repository

    async def update_status(
        self,
        operation_uuid: str,
        status: OperationStatus,
        error: str | None = None,
    ) -> None:
        await self.operations_repository.update_status(
            operation_uuid=operation_uuid,
            status=status,
            error=error,
        )
