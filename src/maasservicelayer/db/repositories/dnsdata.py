#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from typing import Type

from sqlalchemy import Table

from maasservicelayer.db.repositories.base import BaseRepository
from maasservicelayer.db.tables import DNSDataTable
from maasservicelayer.models.dnsdata import DNSData


class DNSDataRepository(BaseRepository[DNSData]):
    def get_repository_table(self) -> Table:
        return DNSDataTable

    def get_model_factory(self) -> Type[DNSData]:
        return DNSData
