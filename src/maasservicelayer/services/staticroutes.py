# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesRepository,
)
from maasservicelayer.models.staticroutes import StaticRoute
from maasservicelayer.services._base import BaseService


class StaticRoutesService(BaseService[StaticRoute, StaticRoutesRepository]):
    def __init__(
        self, context: Context, staticroutes_repository: StaticRoutesRepository
    ):
        super().__init__(context, staticroutes_repository)
