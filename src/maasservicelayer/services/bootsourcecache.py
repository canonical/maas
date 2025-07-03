# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bootsourcecache import BootSourceCacheBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourcecache import (
    BootSourceCacheRepository,
)
from maasservicelayer.models.bootsourcecache import BootSourceCache
from maasservicelayer.services.base import BaseService, ServiceCache


class BootSourceCacheService(
    BaseService[
        BootSourceCache, BootSourceCacheRepository, BootSourceCacheBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootSourceCacheRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
