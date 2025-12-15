# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.legacybootsourceselections import (
    LegacyBootSourceSelectionBuilder,
)
from maasservicelayer.db.repositories.legacybootsourceselections import (
    LegacyBootSourceSelectionRepository,
)
from maasservicelayer.models.legacybootsourceselections import (
    LegacyBootSourceSelection,
)
from maasservicelayer.services.base import BaseService


# TODO: MAASENG-5738 remove this
class LegacyBootSourceSelectionService(
    BaseService[
        LegacyBootSourceSelection,
        LegacyBootSourceSelectionRepository,
        LegacyBootSourceSelectionBuilder,
    ]
):
    """Never use this service directly in API v3.
    It is only used by the BootSourceSelectionService.
    """

    ...
