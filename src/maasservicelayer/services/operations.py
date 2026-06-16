# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.operations import OperationStatus
from maasservicelayer.builders.operations import OperationBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.operations import (
    OperationsClauseFactory,
    OperationsRepository,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.operations import Operation
from maasservicelayer.services.base import BaseService
from maasservicelayer.utils.date import utcnow


class OperationsService(
    BaseService[Operation, OperationsRepository, OperationBuilder]
):
    def __init__(
        self,
        context: Context,
        operations_repository: OperationsRepository,
    ):
        super().__init__(context, operations_repository)

    async def update_status(
        self,
        operation_uuid: str,
        status: OperationStatus,
        result: dict | None = None,
        error: str | None = None,
    ) -> Operation:
        builder = OperationBuilder(status=status)
        if status == OperationStatus.RUNNING:
            builder.started = utcnow()
        elif status in (
            OperationStatus.COMPLETED,
            OperationStatus.FAILED,
        ):
            builder.finished = utcnow()
        if result is not None:
            builder.result = result
        elif error is not None:
            builder.result = {"error": error}

        return await self.update_one(
            query=QuerySpec(
                where=OperationsClauseFactory.with_uuid(operation_uuid)
            ),
            builder=builder,
        )

    async def list_for_user(
        self,
        page: int,
        size: int,
        user_id: int,
        can_view_all: bool,
        query: QuerySpec | None = None,
    ) -> ListResult[Operation]:
        if can_view_all:
            return await self.repository.list(
                page=page, size=size, query=query
            )
        user_clause = OperationsClauseFactory.with_user_id(user_id)
        if query and query.where:
            combined = OperationsClauseFactory.and_clauses(
                [query.where, user_clause]
            )
            filtered_query = QuerySpec(where=combined)
        else:
            filtered_query = QuerySpec(where=user_clause)
        return await self.repository.list(
            page=page, size=size, query=filtered_query
        )

    async def get_by_uuid_for_user(
        self,
        uuid: str,
        user_id: int,
        can_view_all: bool,
    ) -> Operation:
        operation = await self.repository.get_by_uuid(uuid)
        if operation is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Operation with uuid '{uuid}' was not found.",
                    )
                ]
            )
        if can_view_all:
            return operation
        if operation.user_id != user_id:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Operation with uuid '{uuid}' was not found.",
                    )
                ]
            )
        return operation
