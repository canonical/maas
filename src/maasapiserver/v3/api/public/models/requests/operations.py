# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Self
from urllib.parse import quote

from fastapi import Query
from pydantic import BaseModel, Field, model_validator

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.exceptions.catalog import ValidationException
from maasservicelayer.filters.base import Filter
from maasservicelayer.filters.operations import OperationsFilters


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

    resource_type: str | None = Field(
        Query(
            default=None,
            description="Filter by resource type, e.g. 'machine'",
        )
    )

    resource_id: int | None = Field(
        Query(default=None, description="Filter by resource id")
    )

    @model_validator(mode="after")
    def validate_resource_filter(self) -> Self:
        if self.resource_id is not None and self.resource_type is None:
            raise ValidationException.build_for_field(
                "resource_type",
                "Missing 'resource_type' query parameter. You must "
                "specify resource_type when filtering by resource_id.",
                location="query",
            )
        return self

    def to_filter(self) -> Filter | None:
        filters = []
        if self.status is not None:
            filters.append(OperationsFilters.with_status(self.status))
        if self.op_type is not None:
            filters.append(OperationsFilters.with_op_type(self.op_type))
        if self.is_bulk is not None:
            filters.append(OperationsFilters.with_is_bulk(self.is_bulk))
        if self.resource_type is not None:
            filters.append(
                OperationsFilters.with_resource_type(self.resource_type)
            )
        if self.resource_id is not None:
            filters.append(
                OperationsFilters.with_resource_id(self.resource_id)
            )
        if len(filters) == 0:
            return None
        elif len(filters) == 1:
            return filters[0]
        else:
            return OperationsFilters.and_filters(filters)

    def to_href_format(self) -> str:
        parts = []
        if self.status is not None:
            parts.append(f"status={self.status}")
        if self.op_type is not None:
            parts.append(f"op_type={self.op_type}")
        if self.is_bulk is not None:
            parts.append(f"is_bulk={str(self.is_bulk).lower()}")
        if self.resource_type is not None:
            parts.append(f"resource_type={quote(self.resource_type)}")
        if self.resource_id is not None:
            parts.append(f"resource_id={self.resource_id}")

        return "&".join(parts) if parts else ""
