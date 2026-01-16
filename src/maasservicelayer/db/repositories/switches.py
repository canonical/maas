#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table
from sqlalchemy.sql.operators import eq

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import SwitchTable, SwitchInterfaceTable
from maasservicelayer.models.switches import Switch, SwitchInterface


class SwitchClauseFactory(ClauseFactory):
    """Factory for creating query clauses for Switch queries."""

    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SwitchTable.c.id, id))

    @classmethod
    def with_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=SwitchTable.c.id.in_(ids))

    @classmethod
    def with_hostname(cls, hostname: str) -> Clause:
        return Clause(condition=eq(SwitchTable.c.hostname, hostname))

    @classmethod
    def with_vendor(cls, vendor: str) -> Clause:
        return Clause(condition=eq(SwitchTable.c.vendor, vendor))

    @classmethod
    def with_state(cls, state: str) -> Clause:
        return Clause(condition=eq(SwitchTable.c.state, state))

    @classmethod
    def with_serial_number(cls, serial_number: str) -> Clause:
        return Clause(condition=eq(SwitchTable.c.serial_number, serial_number))


class SwitchInterfaceClauseFactory(ClauseFactory):
    """Factory for creating query clauses for SwitchInterface queries."""

    @classmethod
    def with_id(cls, id: int) -> Clause:
        return Clause(condition=eq(SwitchInterfaceTable.c.id, id))

    @classmethod
    def with_switch_id(cls, switch_id: int) -> Clause:
        return Clause(condition=eq(SwitchInterfaceTable.c.switch_id, switch_id))

    @classmethod
    def with_mac_address(cls, mac_address: str) -> Clause:
        return Clause(
            condition=eq(SwitchInterfaceTable.c.mac_address, mac_address)
        )


class SwitchesRepository(BaseRepository[Switch]):
    """Repository for managing Switch entities in the database."""

    def get_repository_table(self) -> Table:
        return SwitchTable

    def get_model_factory(self) -> Type[Switch]:
        return Switch


class SwitchInterfacesRepository(BaseRepository[SwitchInterface]):
    """Repository for managing SwitchInterface entities in the database."""

    def get_repository_table(self) -> Table:
        return SwitchInterfaceTable

    def get_model_factory(self) -> Type[SwitchInterface]:
        return SwitchInterface
