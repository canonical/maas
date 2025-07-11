# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from maasservicelayer.builders.bootresourcesets import BootResourceSetBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootresourcesets import (
    BootResourceSetsRepository,
)
from maasservicelayer.models.bootresourcesets import BootResourceSet
from maasservicelayer.services.base import BaseService, ServiceCache


class BootResourceSetsService(
    BaseService[
        BootResourceSet, BootResourceSetsRepository, BootResourceSetBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootResourceSetsRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
