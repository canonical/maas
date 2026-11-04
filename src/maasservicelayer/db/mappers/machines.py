# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Any

from sqlalchemy import func, Select, select
from sqlalchemy.sql.operators import eq

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.db.mappers.base import ColumnMapping
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    BMCTable,
    DomainTable,
    NodeTable,
    UserTable,
)
from maasservicelayer.models.machines import Machine


class MachineDomainDataMapper(DefaultDomainDataMapper[Machine]):
    def field_mappings(self) -> dict[str, ColumnMapping]:
        return {
            "owner": ColumnMapping(
                UserTable.c.username,
                (
                    NodeTable.outerjoin(
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

    def select_statement(self) -> Select[Any]:
        return (
            select(
                NodeTable.c.id,
                NodeTable.c.system_id,
                NodeTable.c.created,
                NodeTable.c.updated,
                func.coalesce(self.field_mappings()["owner"].column, "").label(
                    "owner"
                ),
                NodeTable.c.description,
                NodeTable.c.cpu_speed,
                NodeTable.c.memory,
                NodeTable.c.osystem,
                NodeTable.c.architecture,
                NodeTable.c.distro_series,
                NodeTable.c.hwe_kernel,
                NodeTable.c.locked,
                NodeTable.c.cpu_count,
                NodeTable.c.status,
                NodeTable.c.node_type,
                NodeTable.c.hostname,
                NodeTable.c.power_state,
                NodeTable.c.owner_id,
                NodeTable.c.error_description,
                NodeTable.c.current_commissioning_script_set_id,
                NodeTable.c.current_testing_script_set_id,
                NodeTable.c.current_installation_script_set_id,
                NodeTable.c.pool_id,
                BMCTable.c.power_type,
                func.concat(
                    NodeTable.c.hostname, ".", DomainTable.c.name
                ).label("fqdn"),
            )
            .select_from(NodeTable)
            .join(
                DomainTable,
                eq(DomainTable.c.id, NodeTable.c.domain_id),
                isouter=True,
            )
            .join(
                UserTable,
                eq(UserTable.c.id, NodeTable.c.owner_id),
                isouter=True,
            )
            .join(
                BMCTable, eq(BMCTable.c.id, NodeTable.c.bmc_id), isouter=True
            )
            .where(eq(NodeTable.c.node_type, NodeTypeEnum.MACHINE))
        )
