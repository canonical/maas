# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import func

from maasservicelayer.db.mappers.base import ColumnMapping
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    BMCTable,
    DomainTable,
    NodeTable,
    UserTable,
)


class MachineDomainDataMapper(DefaultDomainDataMapper):
    def field_mappings(self) -> dict[str, ColumnMapping]:
        return {
            "owner": ColumnMapping(
                UserTable.c.username,
                (
                    NodeTable.join(
                        UserTable, UserTable.c.id == NodeTable.c.owner_id
                    ),
                ),
            ),
            "power_type": ColumnMapping(
                BMCTable.c.power_type,
                (
                    NodeTable.outerjoin(
                        BMCTable, BMCTable.c.id == NodeTable.c.bmc_id
                    ),
                ),
            ),
            "fqdn": ColumnMapping(
                func.concat(NodeTable.c.hostname, ".", DomainTable.c.name),
                (
                    NodeTable.outerjoin(
                        DomainTable, DomainTable.c.id == NodeTable.c.domain_id
                    ),
                ),
            ),
        }
