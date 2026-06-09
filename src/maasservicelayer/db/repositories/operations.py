# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import update

from maascommon.enums.operations import OperationStatus
from maasservicelayer.db.repositories.base import Repository
from maasservicelayer.db.tables import OperationTable
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.utils.date import utcnow


class OperationsRepository(Repository):
    """Repository for managing long-running operations."""

    async def update_status(
        self,
        operation_uuid: str,
        status: OperationStatus,
        error: str | None = None,
    ) -> None:
        now = utcnow()
        values: dict = {"status": status, "updated_at": now}
        if status == OperationStatus.RUNNING:
            values["started_at"] = now
        elif status in (
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
        ):
            values["finished_at"] = now
        if error is not None:
            values["result_errors"] = {"error": error}

        stmt = (
            update(OperationTable)
            .where(OperationTable.c.uuid == operation_uuid)
            .values(**values)
            .returning(OperationTable.c.uuid)
        )
        row = (await self.execute_stmt(stmt)).one_or_none()
        if row is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message="Resource with such identifiers does not exist.",
                    )
                ]
            )
