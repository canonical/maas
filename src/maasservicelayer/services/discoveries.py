# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.context import Context
from maasservicelayer.db.repositories.discoveries import DiscoveriesRepository
from maasservicelayer.models.discoveries import Discovery
from maasservicelayer.services.base import ReadOnlyService


class DiscoveriesService(ReadOnlyService[Discovery, DiscoveriesRepository]):
    def __init__(
        self,
        context: Context,
        discoveries_repository: DiscoveriesRepository,
    ):
        super().__init__(context, discoveries_repository)
