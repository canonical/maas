# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar, Iterable

from maascommon.enums.operations import OperationStatus, OperationType
from maasservicelayer.filters.base import (
    CustomFilter,
    FieldFilter,
    FilterFactory,
)
from maasservicelayer.models.operations import Operation


@dataclass(frozen=True)
class OperationsCreatedBefore(CustomFilter):
    model: ClassVar[type[Operation]] = Operation
    moment: datetime


class OperationsFilters(FilterFactory):
    model = Operation

    @classmethod
    def with_uuid(cls, uuid: str) -> FieldFilter:
        return cls._equals("uuid", uuid)

    @classmethod
    def with_uuids(cls, uuids: Iterable[str]) -> FieldFilter:
        return cls._is_in("uuid", uuids)

    @classmethod
    def with_status(cls, status: OperationStatus) -> FieldFilter:
        return cls._equals("status", status)

    @classmethod
    def with_statuses(cls, statuses: Iterable[OperationStatus]) -> FieldFilter:
        return cls._is_in("status", statuses)

    @classmethod
    def with_op_type(cls, op_type: OperationType) -> FieldFilter:
        return cls._equals("op_type", op_type)

    @classmethod
    def with_is_bulk(cls, is_bulk: bool) -> FieldFilter:
        return cls._equals("is_bulk", is_bulk)

    @classmethod
    def with_resource_type(cls, resource_type: str) -> FieldFilter:
        return cls._equals("resource_type", resource_type)

    @classmethod
    def with_resource_id(cls, resource_id: int) -> FieldFilter:
        return cls._equals("resource_id", resource_id)

    @classmethod
    def with_user_id(cls, user_id: int) -> FieldFilter:
        return cls._equals("user_id", user_id)

    @classmethod
    def created_before(cls, moment: datetime) -> OperationsCreatedBefore:
        return OperationsCreatedBefore(moment)
