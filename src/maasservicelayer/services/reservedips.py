# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.reservedips import ReservedIPsRepository
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.services._base import BaseService


class ReservedIPsService(BaseService[ReservedIP, ReservedIPsRepository]):
    def __init__(
        self, context: Context, reservedips_repository: ReservedIPsRepository
    ):
        super().__init__(context, reservedips_repository)
