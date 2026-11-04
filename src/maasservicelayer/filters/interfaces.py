# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.fields import normalise_macaddress
from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.interfaces import Interface


class InterfaceFilters(FilterFactory):
    model = Interface

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_mac_address(cls, mac_address: str) -> FieldFilter:
        return cls._equals("mac_address", normalise_macaddress(mac_address))

    @classmethod
    def with_vlan_id_in(cls, vlan_ids: list[int]) -> FieldFilter:
        return cls._is_in("vlan_id", vlan_ids)

    @classmethod
    def with_node_config_id(cls, config_id: int) -> FieldFilter:
        return cls._equals("node_config_id", config_id)

    @classmethod
    def with_switch_id(cls, switch_id: int) -> FieldFilter:
        return cls._equals("switch_id", switch_id)
