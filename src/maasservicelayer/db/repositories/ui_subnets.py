# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import cast, String, Table

from maasservicelayer.db.filters import (
    Clause,
    ClauseFactory,
    OrderByClause,
    OrderByClauseFactory,
)
from maasservicelayer.db.repositories.base import ReadOnlyRepository
from maasservicelayer.db.tables import UISubnetView
from maasservicelayer.models.ui_subnets import UISubnet


class UISubnetsClauseFactory(ClauseFactory):
    @classmethod
    def with_cidrs(cls, cidrs: list[str]) -> Clause:
        return Clause(condition=cast(UISubnetView.c.cidr, String).in_(cidrs))

    @classmethod
    def with_vlan_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=UISubnetView.c.vlan_id.in_(ids))

    @classmethod
    def with_fabric_names(cls, names: list[str]) -> Clause:
        return Clause(condition=UISubnetView.c.fabric_name.in_(names))

    @classmethod
    def with_space_names(cls, names: list[str]) -> Clause:
        return Clause(condition=UISubnetView.c.space_name.in_(names))

    @classmethod
    def with_fabric_name_like(cls, partial_name: str) -> Clause:
        return Clause(
            condition=UISubnetView.c.fabric_name.contains(partial_name)
        )

    @classmethod
    def with_vlan_name_like(cls, partial_name: str) -> Clause:
        return Clause(
            condition=UISubnetView.c.vlan_name.contains(partial_name)
        )

    @classmethod
    def with_space_name_like(cls, partial_name: str) -> Clause:
        return Clause(
            condition=UISubnetView.c.space_name.contains(partial_name)
        )

    @classmethod
    def with_cidr_like(cls, partial_cidr: str) -> Clause:
        return Clause(
            condition=cast(UISubnetView.c.cidr, String).contains(partial_cidr)
        )

    @classmethod
    def with_subnet_ids(cls, ids: list[int]) -> Clause:
        return Clause(condition=UISubnetView.c.id.in_(ids))


class UISubnetsOrderByClauses(OrderByClauseFactory):
    @staticmethod
    def by_cidr() -> OrderByClause:
        return OrderByClause(column=UISubnetView.c.cidr)

    @staticmethod
    def by_fabric_name() -> OrderByClause:
        return OrderByClause(column=UISubnetView.c.fabric_name)

    @staticmethod
    def by_space_name() -> OrderByClause:
        return OrderByClause(column=UISubnetView.c.space_name)


class UISubnetsRepository(ReadOnlyRepository[UISubnet]):
    def get_repository_table(self) -> Table:
        return UISubnetView

    def get_model_factory(self) -> Type[UISubnet]:
        return UISubnet
