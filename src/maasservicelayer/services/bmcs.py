#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bmc import BmcBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bmcs import BmcsRepository
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.services.base import BaseService


class BmcsService(BaseService[Bmc, BmcsRepository, BmcBuilder]):
    def __init__(self, context: Context, bmcs_repository: BmcsRepository):
        super().__init__(context, bmcs_repository)
