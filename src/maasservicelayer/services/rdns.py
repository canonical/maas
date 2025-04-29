# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.rdns import RDNSBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.rdns import RDNSRepository
from maasservicelayer.models.rdns import RDNS
from maasservicelayer.services.base import BaseService


class RDNSService(BaseService[RDNS, RDNSRepository, RDNSBuilder]):
    def __init__(self, context: Context, rdns_repository: RDNSRepository):
        super().__init__(context, rdns_repository)
