#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.events import EventTypeEnum
from maascommon.enums.scriptresult import ScriptStatus
from maascommon.node import (
    NODE_FAILURE_STATUS_TRANSITION_MAP,
    NODE_STATUS_LABELS,
)
from maasservicelayer.builders.nodes import NodeBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.nodes import (
    AbstractNodesRepository,
    NodeClauseFactory,
)
from maasservicelayer.models.bmc import Bmc
from maasservicelayer.models.nodes import Node
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.scriptresult import ScriptResultsService
from maasservicelayer.services.secrets import SecretsService


class NodesService(BaseService[Node, AbstractNodesRepository, NodeBuilder]):
    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        events_service: EventsService,
        scriptresults_service: ScriptResultsService,
        nodes_repository: AbstractNodesRepository,
    ):
        super().__init__(context, nodes_repository)
        self.secrets_service = secrets_service
        self.events_service = events_service
        self.scriptresults_service = scriptresults_service

    async def update_by_system_id(
        self, system_id: str, builder: NodeBuilder
    ) -> Node:
        return await self.repository.update_one(
            query=QuerySpec(where=NodeClauseFactory.with_system_id(system_id)),
            builder=builder,
        )

    async def move_to_zone(self, old_zone_id: int, new_zone_id: int) -> None:
        """
        Move all the Nodes from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.repository.move_to_zone(old_zone_id, new_zone_id)

    async def move_bmcs_to_zone(
        self, old_zone_id: int, new_zone_id: int
    ) -> None:
        """
        Move all the BMC from 'old_zone_id' to 'new_zone_id'.
        """
        return await self.repository.move_bmcs_to_zone(
            old_zone_id, new_zone_id
        )

    async def get_bmc(self, system_id: str) -> Bmc | None:
        bmc = await self.repository.get_node_bmc(system_id)
        if bmc is not None:
            secret_power_params = (
                await self.secrets_service.get_composite_secret(
                    f"bmc/{bmc.id}/power_parameters"
                )
            )
            bmc.power_parameters.update(secret_power_params)
        return bmc

    async def hostname_exists(self, hostname: str) -> bool:
        return await self.repository.hostname_exists(hostname)

    async def mark_failed(
        self,
        system_id: str,
        message: str | None,
        script_result_status: ScriptStatus = ScriptStatus.FAILED,
    ) -> Node | None:
        """Mark node as failed."""
        node = await self.repository.get_one(
            query=QuerySpec(where=NodeClauseFactory.with_system_id(system_id))
        )
        if node:
            await self.events_service.record_event(
                node=node,
                event_type=EventTypeEnum.REQUEST_NODE_MARK_FAILED_SYSTEM,
                event_action="mark_failed",
                event_description=message,
            )

            await self.scriptresults_service.update_running_scripts(
                scripts_sets=[
                    node.current_commissioning_script_set_id,
                    node.current_testing_script_set_id,
                    node.current_installation_script_set_id,
                ],
                new_status=script_result_status,
            )

            new_status = NODE_FAILURE_STATUS_TRANSITION_MAP.get(
                node.status, None
            )
            if new_status:
                await self.events_service.record_event(
                    node=node,
                    event_type=EventTypeEnum.NODE_CHANGED_STATUS,
                    event_description=f"From '{NODE_STATUS_LABELS[node.status]}' to '{NODE_STATUS_LABELS[new_status]}'",
                )
                node = await self.repository.update_by_id(
                    node.id,
                    builder=NodeBuilder(
                        status=new_status, error_description=message
                    ),
                )

        return node
