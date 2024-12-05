from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import (
    BaseRepository,
    ResourceBuilder,
)
from maasservicelayer.db.tables import DNSDataTable
from maasservicelayer.models.dnsdata import DNSData


class DNSDataResourceBuilder(ResourceBuilder):
    def with_rrtype(self, value: str) -> "DNSDataResourceBuilder":
        self._request.set_value(DNSDataTable.c.rrtype.name, value)
        return self

    def with_rrdata(self, value: str) -> "DNSDataResourceBuilder":
        self._request.set_value(DNSDataTable.c.rrdata.name, value)
        return self

    def with_dnsresource_id(self, id: int) -> "DNSDataResourceBuilder":
        self._request.set_value(DNSDataTable.c.dnsresource_id.name, id)
        return self

    def with_ttl(self, value: int) -> "DNSDataResourceBuilder":
        self._request.set_value(DNSDataTable.c.ttl.name, value)
        return self


class DNSDataRepository(BaseRepository[DNSData]):
    def get_repository_table(self) -> Table:
        return DNSDataTable

    def get_model_factory(self) -> Type[DNSData]:
        return DNSData
