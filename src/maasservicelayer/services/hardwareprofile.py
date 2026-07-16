# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.scriptresult import ScriptResultsService


class HardwareProfileService(
    BaseService[
        HardwareProfile, HardwareProfileRepository, HardwareProfileBuilder
    ]
):
    resource_logging_name = "hardwareprofile"

    def __init__(
        self,
        context: Context,
        hardware_profile_repository: HardwareProfileRepository,
        scriptresults_service: ScriptResultsService,
    ):
        super().__init__(context, hardware_profile_repository)

    async def create_or_update(
        self, builder: HardwareProfileBuilder
    ) -> HardwareProfile:
        return await self.repository.create_or_update(builder)

    async def initialize(self) -> None:
        """To be called at MAAS startup. Populates all the hardware profiles
        for the already commissioned nodes.
        """
        if await self.exists(QuerySpec()):
            # If at least one profile exists, so we already ran this.
            return
