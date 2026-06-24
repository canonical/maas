# Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.enums.dns import DnsUpdateAction
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
from maasservicelayer.models.secrets import BMCPowerParametersSecret
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.events import EventsService
from maasservicelayer.services.scriptresult import ScriptResultsService
from maasservicelayer.services.secrets import SecretsService
from provisioningserver.drivers.power.registry import sanitise_power_parameters


class NodesService(BaseService[Node, AbstractNodesRepository, NodeBuilder]):
    def __init__(
        self,
        context: Context,
        secrets_service: SecretsService,
        events_service: EventsService,
        scriptresults_service: ScriptResultsService,
        dnspublications_service: DNSPublicationsService,
        nodes_repository: AbstractNodesRepository,
    ):
        super().__init__(context, nodes_repository)
        self.secrets_service = secrets_service
        self.events_service = events_service
        self.scriptresults_service = scriptresults_service
        self.dnspublications_service = dnspublications_service

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
                    BMCPowerParametersSecret(id=bmc.id)
                )
            )
            bmc.power_parameters.update(secret_power_params)
        return bmc

    async def set_bmc(
        self, system_id: str, power_type: str, power_parameters: dict
    ) -> Bmc:
        """Update the BMC power type and parameters for ``system_id``.

        Secret parameters (those flagged ``secret`` by the power driver) are
        extracted and stored in the secret store; only non-secret parameters
        are written to the BMC row. The returned model has the secrets merged
        back in, mirroring :meth:`get_bmc`.

        Raises :class:`NotFoundException` if the machine has no linked BMC.
        Subclasses may override this to add pre-flight validation (e.g. FIPS
        compliance checks) before delegating to this implementation.
        """
        public_params, secrets = sanitise_power_parameters(
            power_type, power_parameters
        )
        bmc = await self.repository.update_node_bmc(
            system_id, power_type, public_params
        )
        if secrets:
            await self.secrets_service.set_composite_secret(
                BMCPowerParametersSecret(id=bmc.id), secrets
            )
            bmc.power_parameters.update(secrets)
        return bmc

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
                event_description=message or "",
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
                        status=new_status, error_description=message or ""
                    ),
                )

        return node

    async def post_update_hook(
        self, old_resource: Node, updated_resource: Node
    ) -> None:
        if old_resource.hostname != updated_resource.hostname:
            await self.dnspublications_service.create_for_config_update(
                action=DnsUpdateAction.RELOAD,
                source=f"node {old_resource.hostname} renamed to {updated_resource.hostname}",
            )

        if (
            old_resource.boot_interface_id
            and old_resource.boot_interface_id
            != updated_resource.boot_interface_id
        ):
            await self.dnspublications_service.create_for_config_update(
                action=DnsUpdateAction.RELOAD,
                source=f"node {updated_resource.hostname} changed boot interface",
            )

        if old_resource.domain_id != updated_resource.domain_id:
            await self.dnspublications_service.create_for_config_update(
                action=DnsUpdateAction.RELOAD,
                source=f"node {updated_resource.hostname} changed zone",
            )

    async def post_delete_hook(self, resource: Node) -> None:
        await self.dnspublications_service.create_for_config_update(
            action=DnsUpdateAction.RELOAD,
            source=f"node {resource.hostname} deleted",
        )
