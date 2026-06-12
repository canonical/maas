# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from fastapi import Query
from pydantic import BaseModel, Field

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.db.filters import Clause
from maasservicelayer.db.repositories.operations import OperationsClauseFactory


class OperationFilterParams(BaseModel):
    status: OperationStatus | None = Field(
        Query(default=None, description="Filter by operation status")
    )

    op_type: OperationType | None = Field(
        Query(default=None, description="Filter by operation type")
    )

    is_bulk: bool | None = Field(
        Query(
            default=None,
            description="Filter by whether operation is bulk (True) or individual (False)",
        )
    )

    def to_clause(self) -> Clause | None:
        clauses = []
        if self.status is not None:
            clauses.append(OperationsClauseFactory.with_status(self.status))
        if self.op_type is not None:
            clauses.append(OperationsClauseFactory.with_op_type(self.op_type))
        if self.is_bulk is not None:
            clauses.append(OperationsClauseFactory.with_is_bulk(self.is_bulk))
        if len(clauses) == 0:
            return None
        elif len(clauses) == 1:
            return clauses[0]
        else:
            return OperationsClauseFactory.and_clauses(clauses)

    def to_href_format(self) -> str:
        parts = []
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.op_type is not None:
            parts.append(f"op_type={self.op_type}")
        if self.is_bulk is not None:
            parts.append(f"is_bulk={str(self.is_bulk).lower()}")

        return "&".join(parts) if parts else ""
