# Copyright 2024-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from typing import List

from maascommon.enums.ipaddress import IpAddressFamily, IpAddressType
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
    merge_configure_dhcp_param,
)
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
)
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressRepository,
)
from maasservicelayer.models.fields import MacAddress
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.services.base import BaseService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.temporal import TemporalService


class StaticIPAddressService(
    BaseService[
        StaticIPAddress, StaticIPAddressRepository, StaticIPAddressBuilder
    ]
):
    def __init__(
        self,
        context: Context,
        temporal_service: TemporalService,
        dnsresources_service: DNSResourcesService,
        staticipaddress_repository: StaticIPAddressRepository,
    ):
        super().__init__(context, staticipaddress_repository)
        self.temporal_service = temporal_service
        self.dnsresources_service = dnsresources_service

    async def post_create_hook(self, resource: StaticIPAddress) -> None:
        if resource.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[resource.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return

    async def post_update_hook(
        self, old_resource: StaticIPAddress, updated_resource: StaticIPAddress
    ) -> None:
        if updated_resource.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[updated_resource.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return

    async def post_update_many_hook(
        self, resources: List[StaticIPAddress]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def create_or_update(
        self, builder: StaticIPAddressBuilder
    ) -> StaticIPAddress:
        ip = await self.repository.create_or_update(builder)
        if ip.alloc_type != IpAddressType.DISCOVERED:
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(static_ip_addr_ids=[ip.id]),
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )
        return ip

    async def pre_delete_hook(
        self, resource_to_be_deleted: StaticIPAddress
    ) -> None:
        # Remove this StaticIPAddress from the many to many relations first.
        # Capture DNS resources before unlinking them
        # This mimics Django signal behavior from:
        # src/maasserver/models/signals/staticipaddress.py:pre_delete_record_relations_on_delete
        dnsresources_to_cleanup = (
            await self.dnsresources_service.get_dnsresources_for_ip(
                resource_to_be_deleted
            )
        )

        # Remove this StaticIPAddress from all many-to-many relations
        await self.repository.unlink_from_interfaces(
            staticipaddress_id=resource_to_be_deleted.id
        )
        await self.dnsresources_service.unlink_ip_from_all_dnsresources(
            staticipaddress_id=resource_to_be_deleted.id
        )

        if not dnsresources_to_cleanup:
            return

        dnsresource_ids = [dnsrr.id for dnsrr in dnsresources_to_cleanup]
        orphaned_ids = (
            await self.dnsresources_service.get_dnsresources_without_ips(
                dnsresource_ids
            )
        )

        if orphaned_ids:
            to_delete_ids = await self.dnsresources_service.get_dnsresources_without_dnsdata(
                orphaned_ids
            )
            if to_delete_ids:
                await self.dnsresources_service.delete_many(
                    QuerySpec(
                        where=DNSResourceClauseFactory.with_ids(to_delete_ids)
                    )
                )

    async def post_delete_hook(self, resource: StaticIPAddress) -> None:
        if (
            resource.alloc_type != IpAddressType.DISCOVERED
            and resource.subnet_id is not None
        ):
            self.temporal_service.register_or_update_workflow_call(
                CONFIGURE_DHCP_WORKFLOW_NAME,
                ConfigureDHCPParam(
                    subnet_ids=[resource.subnet_id]
                ),  # use parent id on delete
                parameter_merge_func=merge_configure_dhcp_param,
                wait=False,
            )

    async def post_delete_many_hook(
        self, resources: List[StaticIPAddress]
    ) -> None:
        raise NotImplementedError("Not implemented yet.")

    async def get_discovered_ips_in_family_for_interfaces(
        self,
        interfaces: list[Interface],
        family: IpAddressFamily = IpAddressFamily.IPV4,
    ) -> List[StaticIPAddress]:
        return (
            await self.repository.get_discovered_ips_in_family_for_interfaces(
                interfaces, family=family
            )
        )

    async def get_for_interfaces(
        self, interface_ids: list[int]
    ) -> list[StaticIPAddress]:
        return await self.repository.get_for_interfaces(interface_ids)

    async def get_for_nodes(self, query: QuerySpec) -> list[StaticIPAddress]:
        return await self.repository.get_for_nodes(query=query)

    async def get_mac_addresses(self, query: QuerySpec) -> list[MacAddress]:
        return await self.repository.get_mac_addresses(query=query)

    async def update_many(
        self, query: QuerySpec, builder: StaticIPAddressBuilder
    ) -> List[StaticIPAddress]:
        updated_resources = await self.repository.update_many(
            query=query, builder=builder
        )

        if builder.must_trigger_workflow():
            await self.post_update_many_hook(updated_resources)
        return updated_resources

    async def get_ip_addresses_for_interface(
        self, interface_id: int
    ) -> list[StaticIPAddress]:
        """Get all IP addresses associated with a specific interface.

        Args:
            interface_id: The ID of the interface

        Returns:
            List of StaticIPAddress objects linked to this interface
        """
        return await self.repository.get_ip_addresses_for_interface(
            interface_id
        )

    async def has_linked_interfaces(self, staticipaddress_id: int) -> bool:
        """Check if a static IP address has any linked interfaces.

        Args:
            staticipaddress_id: The ID of the IP address

        Returns:
            True if the IP has at least one linked interface, False otherwise
        """
        return await self.repository.has_linked_interfaces(staticipaddress_id)

    async def delete_ips_if_no_linked_interfaces(
        self, staticipaddress_ids: list[int]
    ) -> None:
        """Delete static IPs when no interfaces are associated with them.

        Args:
            staticipaddress_ids: The IDs of the IP addresses

        """
        await self.repository.delete_ips_if_no_linked_interfaces(
            staticipaddress_ids
        )
