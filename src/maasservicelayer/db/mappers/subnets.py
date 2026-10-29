# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join, or_

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import SubnetTable, VlanTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.subnets import (
    SubnetCIDROverlapFilter,
    SubnetFabricFilter,
    SubnetRdnsModeNotFilter,
)


class SubnetDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case SubnetFabricFilter(fabric_id):
                return Clause(
                    condition=VlanTable.c.fabric_id == fabric_id,
                    joins=[
                        join(
                            SubnetTable,
                            VlanTable,
                            SubnetTable.c.vlan_id == VlanTable.c.id,
                        )
                    ],
                )
            case SubnetRdnsModeNotFilter(rdns_mode):
                return Clause(condition=SubnetTable.c.rdns_mode != rdns_mode)
            case SubnetCIDROverlapFilter(cidr):
                return Clause(
                    condition=or_(
                        SubnetTable.c.cidr.op(">>")(cidr),
                        SubnetTable.c.cidr.op("<<")(cidr),
                    )
                )
            case _:
                return super().custom_filter_clause(filter)
