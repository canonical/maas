# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import StaticRouteTable, SubnetTable, VlanTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.staticroutes import WithFabricId, WithVlanId


class StaticRouteDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case WithVlanId(vlan_id):
                return Clause(
                    condition=SubnetTable.c.vlan_id == vlan_id,
                    joins=[
                        join(
                            StaticRouteTable,
                            SubnetTable,
                            SubnetTable.c.id == StaticRouteTable.c.source_id,
                        )
                    ],
                )
            case WithFabricId(fabric_id):
                return Clause(
                    condition=VlanTable.c.fabric_id == fabric_id,
                    joins=[
                        join(
                            StaticRouteTable,
                            SubnetTable,
                            SubnetTable.c.id == StaticRouteTable.c.source_id,
                        ),
                        join(
                            SubnetTable,
                            VlanTable,
                            SubnetTable.c.vlan_id == VlanTable.c.id,
                        ),
                    ],
                )
            case _:
                return super().custom_filter_clause(filter)
