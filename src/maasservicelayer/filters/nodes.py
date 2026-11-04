# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.node import NodeTypeEnum
from maasservicelayer.filters.base import FieldFilter, FilterFactory
from maasservicelayer.models.nodes import Node


class NodeFilters(FilterFactory):
    model = Node

    @classmethod
    def with_id(cls, id: int) -> FieldFilter:
        return cls._equals("id", id)

    @classmethod
    def with_ids(cls, ids: list[int]) -> FieldFilter:
        return cls._is_in("id", ids)

    @classmethod
    def with_hostname(cls, hostname: str | None) -> FieldFilter:
        return cls._equals("hostname", hostname)

    @classmethod
    def with_system_id(cls, system_id: str) -> FieldFilter:
        return cls._equals("system_id", system_id)

    @classmethod
    def with_type(cls, value: NodeTypeEnum) -> FieldFilter:
        return cls._equals("node_type", value)

    @classmethod
    def with_owner_id(cls, owner_id: int) -> FieldFilter:
        return cls._equals("owner_id", owner_id)

    @classmethod
    def with_node_config_id(cls, node_config_id: int) -> FieldFilter:
        return cls._equals("current_config_id", node_config_id)
