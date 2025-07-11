# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.bootsourceselections import (
    BootSourceSelectionBuilder,
)
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.bootsourceselections import (
    BootSourceSelectionsRepository,
)
from maasservicelayer.models.bootsourceselections import BootSourceSelection
from maasservicelayer.services.base import BaseService, ServiceCache


class BootSourceSelectionsService(
    BaseService[
        BootSourceSelection,
        BootSourceSelectionsRepository,
        BootSourceSelectionBuilder,
    ]
):
    def __init__(
        self,
        context: Context,
        repository: BootSourceSelectionsRepository,
        cache: ServiceCache | None = None,
    ):
        super().__init__(context, repository, cache)
