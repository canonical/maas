#  Copyright 2024-2025 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime

from netaddr import IPNetwork
from pydantic import IPvAnyAddress
import structlog

from maascommon.enums.ipaddress import IpAddressType, LeaseAction
from maasservicelayer.builders.staticipaddress import StaticIPAddressBuilder
from maasservicelayer.context import Context
from maasservicelayer.db.filters import ClauseFactory, QuerySpec
from maasservicelayer.db.repositories.staticipaddress import (
    StaticIPAddressClauseFactory,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.leases import Lease
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services.base import Service
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService

logger = structlog.getLogger()


class LeaseUpdateError(Exception):
    pass


def _is_valid_hostname(hostname):
    return (
        hostname is not None
        and len(hostname) > 0
        and not hostname.isspace()
        and hostname != "(none)"
    )


class LeasesService(Service):
    def __init__(
        self,
        context: Context,
        dnsresource_service: DNSResourcesService,
        node_service: NodesService,
        staticipaddress_service: StaticIPAddressService,
        subnet_service: SubnetsService,
        interface_service: InterfacesService,
        iprange_service: IPRangesService,
    ):
        super().__init__(context)
        self.dnsresource_service = dnsresource_service
        self.node_service = node_service
        self.staticipaddress_service = staticipaddress_service
        self.subnet_service = subnet_service
        self.interface_service = interface_service
        self.iprange_service = iprange_service

    async def store_lease_info(self, lease: Lease) -> None:
        # Get the subnet for this IP address. If no subnet exists then something
        # is wrong as we should not be receiving message about unknown subnets.
        subnet = await self.subnet_service.find_best_subnet_for_ip(lease.ip)

        if subnet is None:
            raise LeaseUpdateError(f"No subnet exists for: {lease.ip}")

        # Check that the subnet family is the same.
        subnet_network = IPNetwork(str(subnet.cidr))
        if lease.ip_family != subnet_network.version:
            raise LeaseUpdateError(
                f"Family for the subnet does not match. Expected: {lease.ip_family}"
            )

        created = datetime.fromtimestamp(lease.timestamp_epoch)
        logger.info(
            "Lease update: %s for %s on %s at %s%s%s"
            % (
                lease.action,
                lease.ip,
                lease.mac,
                created,
                (
                    " (lease time: %ss)" % lease.lease_time_seconds
                    if lease.lease_time_seconds is not None
                    else ""
                ),
                (
                    " (hostname: %s)" % lease.hostname
                    if _is_valid_hostname(lease.hostname)
                    else ""
                ),
            )
        )

        # We will receive actions on all addresses in the subnet. We only want
        # to update the addresses in the dynamic range.
        dynamic_range = await self.iprange_service.get_dynamic_range_for_ip(
            subnet.id, lease.ip
        )
        if dynamic_range is None:
            return

        interfaces = await self.interface_service.get_interfaces_for_mac(
            lease.mac
        )
        if len(interfaces) == 0:
            if lease.action == LeaseAction.COMMIT:
                # A MAC address that is unknown to MAAS was given an IP address. Create
                # an unknown interface for this lease.
                interfaces = [
                    (
                        await self.interface_service.create_unkwnown_interface(
                            lease.mac, subnet.vlan_id
                        )
                    )
                ]

        sip = None
        # Delete all discovered IP addresses attached to all interfaces of the same
        # IP address family.
        old_family_addresses = await self.staticipaddress_service.get_discovered_ips_in_family_for_interfaces(
            interfaces,
            family=lease.ip_family,
        )
        for address in old_family_addresses:
            # Release old DHCP hostnames, but only for obsolete dynamic addresses.
            if address.ip != lease.ip:
                if address.ip is not None:
                    await self.dnsresource_service.release_dynamic_hostname(
                        address
                    )
                    await self.staticipaddress_service.delete_by_id(address.id)
                else:
                    # Avoid recreating a new StaticIPAddress later.
                    sip = address

        # Create the new StaticIPAddress object based on the action.
        match lease.action:
            case LeaseAction.COMMIT.value:
                # Interfaces received a new lease. Create the new object with the updated lease information.
                await self._commit_lease_info(
                    hostname=lease.hostname,
                    subnet=subnet,
                    ip=lease.ip,
                    lease_time=lease.lease_time_seconds,
                    created=created,
                    interfaces=interfaces,
                )
            case LeaseAction.EXPIRY.value | LeaseAction.RELEASE.value:
                # Interfaces no longer holds an active lease. Create the new object
                # to show that it used to be connected to this subnet.
                await self._release_lease_info(sip, interfaces, subnet)

    async def _commit_lease_info(
        self,
        hostname: str,
        subnet: Subnet,
        ip: IPvAnyAddress,
        lease_time: int,
        created: datetime,
        interfaces: list[Interface],
    ) -> None:
        # Hostname sent from the cluster is either blank or can be "(none)". In either of those cases we do not set the hostname.
        sip_hostname = None
        if _is_valid_hostname(hostname):
            sip_hostname = hostname

        # Use the timestamp from the lease to create the StaticIPAddress object. That will make sure that the lease_time is correct from the created time.
        sip = await self.staticipaddress_service.create_or_update(
            StaticIPAddressBuilder(
                ip=ip,
                lease_time=lease_time,
                alloc_type=IpAddressType.DISCOVERED,
                subnet_id=subnet.id,
                created=created,
                updated=created,
            )
        )

        for interface in interfaces:
            await self.interface_service.link_ip([interface], sip)
        if sip_hostname is not None:
            # MAAS automatically manages DNS for node hostnames, so we cannot allow a DHCP client to override that.
            node_with_hostname_exists = (
                await self.node_service.hostname_exists(sip_hostname)
            )
            if node_with_hostname_exists:
                # Ensure we don't allow a DHCP hostname to override a node hostname.
                await self.dnsresource_service.release_dynamic_hostname(sip)
            else:
                await self.dnsresource_service.update_dynamic_hostname(
                    sip, sip_hostname
                )

    async def _release_lease_info(
        self,
        sip: StaticIPAddress | None,
        interfaces: list[Interface],
        subnet: Subnet,
    ) -> None:
        if sip is None:
            # XXX: There shouldn't be more than one StaticIPAddress
            #      record here, but it can happen be due to bug 1817305.
            sip = await self.staticipaddress_service.get_one(
                query=QuerySpec(
                    where=ClauseFactory.and_clauses(
                        [
                            StaticIPAddressClauseFactory.with_ip(ip=None),
                            StaticIPAddressClauseFactory.with_subnet_id(
                                subnet_id=subnet.id
                            ),
                            StaticIPAddressClauseFactory.with_alloc_type(
                                alloc_type=IpAddressType.DISCOVERED
                            ),
                            StaticIPAddressClauseFactory.with_interface_ids(
                                interface_ids=[
                                    interface.id for interface in interfaces
                                ]
                            ),
                        ]
                    )
                )
            )
            if sip is None:
                sip = await self.staticipaddress_service.create(
                    StaticIPAddressBuilder(
                        ip=None,
                        lease_time=0,
                        alloc_type=IpAddressType.DISCOVERED,
                        subnet_id=subnet.id,
                    )
                )
        else:
            await self.staticipaddress_service.update_by_id(
                sip.id,
                StaticIPAddressBuilder(
                    ip=None,
                ),
            )

        await self.interface_service.link_ip(interfaces, sip)
