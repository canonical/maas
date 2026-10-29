# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import ReservedIPTable, SubnetTable, VlanTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.reservedips import WithFabricId, WithVlanId
from maasservicelayer.models.reservedips import ReservedIP


class ReservedIPDataMapper(DefaultDomainDataMapper[ReservedIP]):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case WithVlanId(vlan_id):
                return Clause(
                    condition=SubnetTable.c.vlan_id == vlan_id,
                    joins=[
                        join(
                            ReservedIPTable,
                            SubnetTable,
                            ReservedIPTable.c.subnet_id == SubnetTable.c.id,
                        )
                    ],
                )
            case WithFabricId(fabric_id):
                return Clause(
                    condition=VlanTable.c.fabric_id == fabric_id,
                    joins=[
                        join(
                            ReservedIPTable,
                            SubnetTable,
                            ReservedIPTable.c.subnet_id == SubnetTable.c.id,
                        ),
                        join(
                            VlanTable,
                            SubnetTable,
                            VlanTable.c.id == SubnetTable.c.vlan_id,
                        ),
                    ],
                )
            case _:
                return super().custom_filter_clause(filter)
