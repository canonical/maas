# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from operator import eq
from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.filters import Clause, ClauseFactory
from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import NodeGroupToRackControllerTable
from maasservicelayer.models.nodegrouptorackcontrollers import (
    NodeGroupToRackController,
)


class NodeGroupToRackControllersClauseFactory(ClauseFactory):
    @classmethod
    def with_subnet_id(cls, subnet_id: int) -> Clause:
        return Clause(
            condition=eq(NodeGroupToRackControllerTable.c.subnet_id, subnet_id)
        )


class NodeGroupToRackControllersRepository(
    BaseRepository[NodeGroupToRackController]
):
    def get_repository_table(self) -> Table:
        return NodeGroupToRackControllerTable

    def get_model_factory(self) -> Type[NodeGroupToRackController]:
        return NodeGroupToRackController
