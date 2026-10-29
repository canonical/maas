# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.service import ServiceName
from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.service_status import ServiceStatus


class ServiceStatusFilters(FilterFactory):
    model = ServiceStatus

    @classmethod
    def with_name(cls, name: ServiceName) -> FieldFilter:
        return cls._equals("name", name)

    @classmethod
    def with_node_id(cls, id: int) -> FieldFilter:
        return cls._equals("node_id", id)
