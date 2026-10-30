# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import Select, select

from maasservicelayer.db.mappers.base import StorageRow
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    DomainTable,
    ForwardDNSServerDomainsTable,
)
from maasservicelayer.models.forwarddnsserver import ForwardDNSServer


class ForwardDNSServerProjectionDataMapper(
    DefaultDomainDataMapper[ForwardDNSServer]
):
    """The server portion of a joined domain and forwarding-server row."""

    def select_statement(self) -> Select[Any]:
        return (
            select(
                DomainTable,
                *(
                    self.table.c[name].label(f"fdns_{name}")
                    for name in self.model.model_fields
                ),
            )
            .select_from(DomainTable)
            .join(
                ForwardDNSServerDomainsTable,
                ForwardDNSServerDomainsTable.c.domain_id == DomainTable.c.id,
            )
            .join(
                self.table,
                self.table.c.id
                == ForwardDNSServerDomainsTable.c.forwarddnsserver_id,
            )
        )

    def to_domain(self, row: StorageRow) -> ForwardDNSServer:
        return super().to_domain(
            {name: row[f"fdns_{name}"] for name in self.model.model_fields}
        )
