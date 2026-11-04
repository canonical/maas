# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import IPRangeTable, SubnetTable, VlanTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.ipranges import (
    IPRangeFabricFilter,
    IPRangeVlanFilter,
)
from maasservicelayer.models.ipranges import IPRange


class IPRangeDomainDataMapper(DefaultDomainDataMapper[IPRange]):
    @staticmethod
    def _subnet_join():
        return join(
            IPRangeTable,
            SubnetTable,
            SubnetTable.c.id == IPRangeTable.c.subnet_id,
        )

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case IPRangeVlanFilter(vlan_id):
                return Clause(
                    condition=SubnetTable.c.vlan_id == vlan_id,
                    joins=[self._subnet_join()],
                )
            case IPRangeFabricFilter(fabric_id):
                return Clause(
                    condition=VlanTable.c.fabric_id == fabric_id,
                    joins=[
                        self._subnet_join(),
                        join(
                            SubnetTable,
                            VlanTable,
                            SubnetTable.c.vlan_id == VlanTable.c.id,
                        ),
                    ],
                )
            case _:
                return super().custom_filter_clause(filter)
