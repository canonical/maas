# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    InterfaceIPAddressTable,
    InterfaceTable,
    NodeConfigTable,
    NodeTable,
    StaticIPAddressTable,
)
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.staticipaddress import (
    StaticIPAddressAllocTypeNotInFilter,
    StaticIPAddressInterfaceEnabledFilter,
    StaticIPAddressInterfaceIDsFilter,
    StaticIPAddressLinkedToInterfaceFilter,
    StaticIPAddressNodeSystemIDFilter,
    StaticIPAddressNodeTypeFilter,
    StaticIPAddressNotNullFilter,
)


class StaticIPAddressDomainDataMapper(DefaultDomainDataMapper):
    @staticmethod
    def _interface_link_join():
        return join(
            StaticIPAddressTable,
            InterfaceIPAddressTable,
            StaticIPAddressTable.c.id
            == InterfaceIPAddressTable.c.staticipaddress_id,
        )

    @classmethod
    def _interface_joins(cls):
        return [
            cls._interface_link_join(),
            join(
                InterfaceIPAddressTable,
                InterfaceTable,
                InterfaceIPAddressTable.c.interface_id == InterfaceTable.c.id,
            ),
        ]

    @classmethod
    def _node_joins(cls):
        return [
            *cls._interface_joins(),
            join(
                InterfaceTable,
                NodeConfigTable,
                InterfaceTable.c.node_config_id == NodeConfigTable.c.id,
            ),
            join(
                NodeConfigTable,
                NodeTable,
                NodeConfigTable.c.id == NodeTable.c.current_config_id,
            ),
        ]

    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case StaticIPAddressNodeTypeFilter(node_type):
                return Clause(
                    condition=NodeTable.c.node_type == node_type,
                    joins=self._node_joins(),
                )
            case StaticIPAddressNodeSystemIDFilter(system_id):
                return Clause(
                    condition=NodeTable.c.system_id == system_id,
                    joins=self._node_joins(),
                )
            case StaticIPAddressLinkedToInterfaceFilter():
                return Clause(
                    condition=InterfaceIPAddressTable.c.interface_id.is_not(
                        None
                    ),
                    joins=[self._interface_link_join()],
                )
            case StaticIPAddressAllocTypeNotInFilter(alloc_types):
                return Clause(
                    condition=StaticIPAddressTable.c.alloc_type.not_in(
                        alloc_types
                    )
                )
            case StaticIPAddressInterfaceEnabledFilter(enabled):
                return Clause(
                    condition=InterfaceTable.c.enabled == enabled,
                    joins=self._interface_joins(),
                )
            case StaticIPAddressNotNullFilter():
                return Clause(condition=StaticIPAddressTable.c.ip.is_not(None))
            case StaticIPAddressInterfaceIDsFilter(interface_ids):
                return Clause(
                    condition=InterfaceTable.c.id.in_(interface_ids),
                    joins=self._interface_joins(),
                )
            case _:
                return super().custom_filter_clause(filter)
