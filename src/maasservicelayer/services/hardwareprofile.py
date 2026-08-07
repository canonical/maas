# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import json

import structlog

from maasservicelayer.builders.hardwareprofile import HardwareProfileBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.hardwareprofile import (
    HardwareProfileRepository,
)
from maasservicelayer.db.repositories.scriptresults import (
    ScriptResultClauseFactory,
)
from maasservicelayer.models.hardwareprofile import HardwareProfile
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.scriptresult import ScriptResultsService

logger = structlog.getLogger()


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
        self.scriptresults_service = scriptresults_service

    async def create_or_update(
        self, builder: HardwareProfileBuilder
    ) -> HardwareProfile:
        return await self.repository.create_or_update(builder)

    async def populate_all(self):
        """Write the hardware profiles of all nodes which have run a commissioning script.

        This behaves like a migration:
            - if at least one hardware profile exists, do nothing
            - else populate all the hardware profiles

        The reason why this is not part of the hardware profile alembic migration
        is that we don't want to reference code in migrations, as to avoid breaking
        them in the future.
        """
        if await self.exists(QuerySpec()):
            return

        builders = []
        for (
            node_id,
            script_result,
        ) in await self.scriptresults_service.get_latest_for_nodes(
            QuerySpec(
                where=ScriptResultClauseFactory.with_script_name(
                    "50-maas-01-commissioning"
                )
            )
        ):
            try:
                output = json.loads(script_result.output)
                builders.append(HardwareProfileBuilder.from_commissioning_output(
                    output, node_id
                ))
            except Exception:
                # Avoid blocking MAAS start_up if there is a not parsable
                # commissioning script output
                logger.warning(
                    "Failed to populate hardware profile for node "
                    f"'{node_id}', skipping it.",
                    exc_info=True,
                )

        if builders:
            await self.create_many(builders)
