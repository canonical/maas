# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.mdns import MDNSBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.mdns import MDNSRepository
from maasservicelayer.models.mdns import MDNS
from maasservicelayer.services.base import BaseService


class MDNSService(BaseService[MDNS, MDNSRepository, MDNSBuilder]):
    def __init__(self, context: Context, mdns_repository: MDNSRepository):
        super().__init__(context, mdns_repository)
