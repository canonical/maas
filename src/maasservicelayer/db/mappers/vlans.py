# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import or_

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import NodeTable, VlanTable
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.vlans import (
    WithNodeType,
    WithPrimaryOrSecondaryRackId,
    WithRelayVlanExists,
    WithSystemId,
)


class VlanDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case WithSystemId(system_id):
                # get_node_vlans supplies the node/config/interface joins.
                return Clause(condition=NodeTable.c.system_id == system_id)
            case WithNodeType(node_type):
                return Clause(condition=NodeTable.c.node_type == node_type)
            case WithPrimaryOrSecondaryRackId(rack_id):
                return Clause(
                    condition=or_(
                        VlanTable.c.primary_rack_id == rack_id,
                        VlanTable.c.secondary_rack_id == rack_id,
                    )
                )
            case WithRelayVlanExists(exists):
                return Clause(
                    condition=(
                        VlanTable.c.relay_vlan_id.is_not(None)
                        if exists
                        else VlanTable.c.relay_vlan_id.is_(None)
                    )
                )
            case _:
                return super().custom_filter_clause(filter)
