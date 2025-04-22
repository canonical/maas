# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from maascommon.utils.network import MAASIPSet
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.subnet_utilization import (
    SubnetUtilizationRepository,
)
from maasservicelayer.exceptions.catalog import (
    BaseExceptionDetail,
    NotFoundException,
)
from maasservicelayer.exceptions.constants import (
    UNEXISTING_RESOURCE_VIOLATION_TYPE,
)
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.base import Service
from maasservicelayer.services.subnets import SubnetsService


class V3SubnetUtilizationService(Service):
    def __init__(
        self,
        context: Context,
        subnets_service: SubnetsService,
        subnet_utilization_repository: SubnetUtilizationRepository,
    ) -> None:
        super().__init__(context)
        self.repository = subnet_utilization_repository
        self.subnets_service = subnets_service

    async def _get_subnet_or_raise_exception(self, subnet_id: int) -> Subnet:
        subnet = await self.subnets_service.get_by_id(id=subnet_id)
        if subnet is None:
            raise NotFoundException(
                details=[
                    BaseExceptionDetail(
                        type=UNEXISTING_RESOURCE_VIOLATION_TYPE,
                        message=f"Could not find subnet with id {subnet_id}.",
                    )
                ]
            )
        return subnet

    async def get_ipranges_available_for_reserved_range(
        self, subnet_id: int, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Returns a MAASIPSet with the ranges available to allocate a reserved IP range.
        The logic is as follows:
        - Managed subnet
            In use: reserved and dynamic IP ranges
            Available: subnet CIDR - in use
        - Unmanaged subnet:
            In use: reserved IP ranges
            Available: subnet CIDR - in use
        """
        subnet = await self._get_subnet_or_raise_exception(subnet_id)
        return await self.repository.get_ipranges_available_for_reserved_range(
            subnet=subnet, exclude_ip_range_id=exclude_ip_range_id
        )

    async def get_ipranges_available_for_dynamic_range(
        self, subnet_id: int, exclude_ip_range_id: int | None = None
    ) -> MAASIPSet:
        """Returns a MAASIPSet with the ranges available to allocate a dynamic IP range.
        The logic is as follows:
        - Managed subnet
            In use:
              - reserved and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs BUT NOT discovered IPs
            Available: subnet CIDR - in use
        - Unmanaged subnet:
            In use:
              - dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs BUT NOT discovered IPs
            Available: reserved IP ranges - in use
        """
        subnet = await self._get_subnet_or_raise_exception(subnet_id)
        return await self.repository.get_ipranges_available_for_dynamic_range(
            subnet=subnet, exclude_ip_range_id=exclude_ip_range_id
        )

    async def get_ipranges_for_ip_allocation(
        self,
        subnet_id: int,
        exclude_addresses: list[str] | None = None,
    ) -> MAASIPSet:
        """Returns a MAASIPSet with the ranges available to allocate an IP.
        The logic is as follows:
        - Managed subnet
            In use:
              - reserved and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
              - IPs from neighbour observation
            Available: subnet CIDR - in use
        - Unmanaged subnet:
            In use:
              - dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
              - IPs from neighbour observation
            Available: reserved IP ranges - in use
        """
        subnet = await self._get_subnet_or_raise_exception(subnet_id)
        return await self.repository.get_ipranges_for_ip_allocation(
            subnet=subnet,
            exclude_addresses=exclude_addresses,
        )

    async def get_free_ipranges(
        self,
        subnet_id: int,
    ) -> MAASIPSet:
        """Returns a MAASIPSet with the unused ranges for the subnet.
        The logic is as follows:
        - Managed subnet
            In use:
              - reserved and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
            Available: subnet CIDR - in use
        - Unmanaged subnet:
            In use:
              - dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
            Available: reserved IP ranges - in use
        """
        subnet = await self._get_subnet_or_raise_exception(subnet_id)
        return await self.repository.get_free_ipranges(subnet=subnet)

    async def get_subnet_utilization(
        self,
        subnet_id: int,
    ) -> MAASIPSet:
        """Returns a MAASIPSet with both the used and unused ranges for the subnet.
        The logic is as follows:
        - Managed subnet
            In use:
              - reserved and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
            Available: subnet CIDR - in use
        - Unmanaged subnet:
            In use:
              - **reserved** and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
            Available: subnet CIDR - in use
        """
        subnet = await self._get_subnet_or_raise_exception(subnet_id)
        return await self.repository.get_subnet_utilization(subnet=subnet)

    async def get_ipranges_in_use(
        self,
        subnet_id: int,
    ) -> MAASIPSet:
        """Returns a MAASIPSet with the unused ranges for the subnet.
        The logic is as follows:
        - Managed subnet
            In use:
              - reserved and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
        - Unmanaged subnet:
            In use:
              - **reserved** and dynamic IP ranges
              - Subnet’s gateway IP and DNS servers
              - Staticroute’s gateway IP that have the subnet as a “source”
              - Allocated IPs (including discovered IPs)
        """
        subnet = await self._get_subnet_or_raise_exception(subnet_id)
        return await self.repository.get_ipranges_in_use(subnet=subnet)
