# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bootresources import BootResourceBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresources import (
    BootResourcesRepository,
)
from maasservicelayer.models.bootresources import BootResource
from maasservicelayer.services.base import BaseService, ServiceCache


class BootResourceService(
    BaseService[BootResource, BootResourcesRepository, BootResourceBuilder]
):
    def __init__(
        self,
        context: Context,
        repository: BootResourcesRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
