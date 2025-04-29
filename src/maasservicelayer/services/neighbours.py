#  Copyright 2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.neighbours import NeighbourBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.neighbours import NeighboursRepository
from maasservicelayer.models.neighbours import Neighbour
from maasservicelayer.services.base import BaseService


class NeighboursService(
    BaseService[Neighbour, NeighboursRepository, NeighbourBuilder]
):
    def __init__(
        self, context: Context, neighbours_repository: NeighboursRepository
    ):
        super().__init__(context, neighbours_repository)
