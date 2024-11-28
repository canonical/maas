# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
from typing import List

from pydantic import IPvAnyAddress

from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.base import CreateOrUpdateResource
from maasservicelayer.db.repositories.dhcpsnippets import (
    DhcpSnippetsClauseFactory,
)
from maasservicelayer.db.repositories.ipranges import IPRangeClauseFactory
from maasservicelayer.db.repositories.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersClauseFactory,
)
from maasservicelayer.db.repositories.reservedips import (
    ReservedIPsClauseFactory,
)
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.db.repositories.staticroutes import (
    StaticRoutesClauseFactory,
)
from maasservicelayer.db.repositories.subnets import (
    SubnetClauseFactory,
    SubnetsRepository,
)
from maasservicelayer.models.base import ListResult
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service
from maasservicelayer.services.dhcpsnippets import DhcpSnippetsService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodegrouptorackcontrollers import (
    NodeGroupToRackControllersService,
)
from maasservicelayer.services.reservedips import ReservedIPsService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.staticroutes import StaticRoutesService
from maasservicelayer.services.temporal import TemporalService


class SubnetsService(Service):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        staticipaddress_service: StaticIPAddressService,
        ipranges_service: IPRangesService,
        staticroutes_service: StaticRoutesService,
        reservedips_service: ReservedIPsService,
        dhcpsnippets_service: DhcpSnippetsService,
        nodegrouptorackcontrollers_service: NodeGroupToRackControllersService,
        subnets_repository: SubnetsRepository,
    ):
        super().__init__(context)
        self.temporal_service = temporal_service
        self.staticipaddress_service = staticipaddress_service
        self.ipranges_service = ipranges_service
        self.staticroutes_service = staticroutes_service
        self.reservedips_service = reservedips_service
        self.dhcpsnippets_service = dhcpsnippets_service
        self.nodegrouptorackcontrollers = nodegrouptorackcontrollers_service
        self.subnets_repository = subnets_repository

    async def list(
        self, token: str | None, size: int, query: QuerySpec | None = None
    ) -> ListResult[Subnet]:
        return await self.subnets_repository.list(
            token=token, size=size, query=query
        )

    async def get(self, query: QuerySpec) -> List[Subnet]:
        return await self.subnets_repository.get(query)

    async def get_by_id(
        self, fabric_id: int, vlan_id: int, id: int
    ) -> Subnet | None:
        query = QuerySpec(
            where=SubnetClauseFactory.and_clauses(
                [
                    SubnetClauseFactory.with_id(id),
                    SubnetClauseFactory.with_vlan_id(vlan_id),
                    SubnetClauseFactory.with_fabric_id(fabric_id),
                ]
            )
        )
        return await self.subnets_repository.get_one(query=query)

    async def find_best_subnet_for_ip(
        self, ip: IPvAnyAddress
    ) -> Subnet | None:
        return await self.subnets_repository.find_best_subnet_for_ip(ip)

    async def create(self, resource: CreateOrUpdateResource) -> Subnet:
        subnet = await self.subnets_repository.create(resource)
        # TODO: DNS workflow & proxy workflow
        self.temporal_service.register_or_update_workflow_call(
            CONFIGURE_DHCP_WORKFLOW_NAME,
            ConfigureDHCPParam(subnet_ids=[subnet.id]),
            parameter_merge_func=merge_configure_dhcp_param,
            wait=False,
        )
        return subnet

    async def update(
        self, query: QuerySpec, resource: CreateOrUpdateResource
    ) -> Subnet:
        subnet = await self.subnets_repository.update(query, resource)
        if subnet:
            # TODO: DNS workflow & proxy workflow
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(subnet_ids=[subnet.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return subnet

    async def delete(
        self, query: QuerySpec, etag_if_match: str | None = None
    ) -> None:
        if etag_if_match:
            subnet = await self.subnets_repository.get_one(query)
            if not subnet:
                return None
            self.etag_check(subnet, etag_if_match)

        subnet = await self.subnets_repository.delete(query)
        if subnet:
            # cascade delete
            await self.staticipaddress_service.delete(
                QuerySpec(
                    where=StaticIPAddressClauseFactory.with_subnet_id(
                        subnet.id
                    )
                )
            )
            await self.ipranges_service.delete(
                QuerySpec(where=IPRangeClauseFactory.with_subnet_id(subnet.id))
            )
            await self.staticroutes_service.delete(
                QuerySpec(
                    where=StaticRoutesClauseFactory.or_clauses(
                        [
                            StaticRoutesClauseFactory.with_source_id(
                                subnet.id
                            ),
                            StaticRoutesClauseFactory.with_destination_id(
                                subnet.id
                            ),
                        ]
                    )
                )
            )
            await self.reservedips_service.delete(
                QuerySpec(
                    where=ReservedIPsClauseFactory.with_subnet_id(subnet.id)
                )
            )
            await self.dhcpsnippets_service.delete(
                QuerySpec(
                    where=DhcpSnippetsClauseFactory.with_subnet_id(subnet.id)
                )
            )
            await self.nodegrouptorackcontrollers.delete(
                QuerySpec(
                    where=NodeGroupToRackControllersClauseFactory.with_subnet_id(
                        subnet.id
                    )
                )
            )
            # TODO: DNS workflow & proxy workflow
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(
                    vlan_ids=[subnet.vlan_id]
                ),  # use parent when object is deleted
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
