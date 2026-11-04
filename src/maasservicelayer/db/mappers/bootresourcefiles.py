# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from sqlalchemy import join

from maasservicelayer.db.filters import Clause
from maasservicelayer.db.mappers.default import DefaultDomainDataMapper
from maasservicelayer.db.tables import (
    BootResourceFileTable,
    BootResourceSetTable,
)
from maasservicelayer.filters.base import CustomFilter
from maasservicelayer.filters.bootresourcefiles import (
    BootResourceFileSHA256Prefix,
    BootResourceFilesOfResources,
)


class BootResourceFileDomainDataMapper(DefaultDomainDataMapper):
    def custom_filter_clause(self, filter: CustomFilter) -> Clause:
        match filter:
            case BootResourceFileSHA256Prefix(partial_sha256):
                return Clause(
                    condition=BootResourceFileTable.c.sha256.startswith(
                        partial_sha256
                    )
                )
            case BootResourceFilesOfResources(resource_ids):
                return Clause(
                    condition=BootResourceSetTable.c.resource_id.in_(
                        resource_ids
                    ),
                    joins=[
                        join(
                            BootResourceSetTable,
                            BootResourceFileTable,
                            BootResourceSetTable.c.id
                            == BootResourceFileTable.c.resource_set_id,
                        )
                    ],
                )
        return super().custom_filter_clause(filter)
