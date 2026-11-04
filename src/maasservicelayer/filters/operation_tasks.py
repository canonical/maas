# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.operations import OperationTask


class OperationTasksFilters(FilterFactory):
    model = OperationTask

    @classmethod
    def with_operation_uuid(cls, operation_uuid: str) -> FieldFilter:
        return cls._equals("operation_uuid", operation_uuid)
