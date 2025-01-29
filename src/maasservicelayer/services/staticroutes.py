# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesRepository,
)
from maasservicelayer.models.staticroutes import (
    StaticRoute,
    StaticRouteBuilder,
)
from maasservicelayer.services.base import BaseService


class StaticRoutesService(
    BaseService[StaticRoute, StaticRoutesRepository, StaticRouteBuilder]
):
    def __init__(
        self, context: Context, staticroutes_repository: StaticRoutesRepository
    ):
        super().__init__(context, staticroutes_repository)
