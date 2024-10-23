#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from datetime import datetime
from itertools import chain
import re

from netaddr import IPNetwork
from sqlalchemy.ext.asyncio import AsyncConnection

from maascommon.enums.ipaddress import (
    IpAddressFamily,
    IpAddressType,
    LeaseAction,
)
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services._base import Service
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService


class LeaseUpdateError(Exception):
    pass


def _is_valid_hostname(hostname):
    return (
        hostname is not None
        and len(hostname) > 0
        and not hostname.isspace()
        and hostname != "(none)"
    )


MAC_SPLIT_RE = re.compile(r"[-:.]")


def normalise_macaddress(mac: str) -> str:
    tokens = MAC_SPLIT_RE.split(mac.lower())
    match len(tokens):
        case 1:  # no separator
            tokens = re.findall("..", tokens[0])
        case 3:  # each token is two bytes
            tokens = chain(
                *(re.findall("..", token.zfill(4)) for token in tokens)
            )
        case _:  # single-byte tokens
            tokens = (token.zfill(2) for token in tokens)
    return ":".join(tokens)


class LeasesService(Service):
    def __init__(
        self,
        connection: AsyncConnection,
        dnsresource_service: DNSResourcesService,
        node_service: NodesService,
        staticipaddress_service: StaticIPAddressService,
        subnet_service: SubnetsService,
        interface_service: InterfacesService,
        iprange_service: IPRangesService,
    ):
        super().__init__(connection)
        self.dnsresource_service = dnsresource_service
        self.node_service = node_service
        self.staticipaddress_service = staticipaddress_service
        self.subnet_service = subnet_service
        self.interface_service = interface_service
        self.iprange_service = iprange_service

    async def store_lease_info(
        self,
        action: str,
        ip_family: str,
        ip: str,
        mac: str,
        hostname: str,
        timestamp: int,
        lease_time: int,
    ) -> None:
        if action not in (
            LeaseAction.COMMIT.value,
            LeaseAction.EXPIRY.value,
            LeaseAction.RELEASE.value,
        ):
            raise LeaseUpdateError(f"Unknown lease action: {action}")

        subnet = await self.subnet_service.find_best_subnet_for_ip(ip)

        if subnet is None:
            raise LeaseUpdateError(f"No subnet exists for: {ip}")

        subnet_network = IPNetwork(str(subnet.cidr))
        if (
            ip_family == IpAddressFamily.IPV4.name.lower()
            and subnet_network.version != IpAddressFamily.IPV4.value
        ) or (
            ip_family == IpAddressFamily.IPV6.name.lower()
            and subnet_network.version != IpAddressFamily.IPV6.value
        ):
            raise LeaseUpdateError(
                f"Family for the subnet does not match. Expected: {ip_family}"
            )

        mac = normalise_macaddress(mac)
        created = datetime.fromtimestamp(timestamp)

        # We will receive actions on all addresses in the subnet. We only want
        # to update the addresses in the dynamic range.
        dynamic_range = await self.iprange_service.get_dynamic_range_for_ip(
            subnet, ip
        )
        if dynamic_range is None:
            return

        interfaces = await self.interface_service.get_interfaces_for_mac(mac)
        if len(interfaces) == 0:
            if action != LeaseAction.COMMIT:
                return

        sip = None
        old_family_addresses = await self.staticipaddress_service.get_discovered_ips_in_family_for_interfaces(
            interfaces,
            family=(
                IpAddressFamily.IPV4
                if subnet_network.version == IpAddressFamily.IPV4.value
                else IpAddressFamily.IPV6
            ),
        )
        for address in old_family_addresses:
            if address.ip != ip:
                if address.ip is not None:
                    await self.dnsresource_service.release_dynamic_hostname(
                        address
                    )
                    await self.staticipaddress_service.delete(address)
                else:
                    sip = address

        match action:
            case LeaseAction.COMMIT.value:
                await self._commit_lease_info(
                    hostname, subnet, ip, lease_time, created, interfaces
                )
            case LeaseAction.EXPIRY.value:
                await self._release_lease_info(sip, interfaces, subnet)
            case LeaseAction.RELEASE.value:
                await self._release_lease_info(sip, interfaces, subnet)

    async def _commit_lease_info(
        self,
        hostname: str,
        subnet: Subnet,
        ip: str,
        lease_time: int,
        created: datetime,
        interfaces: list[Interface],
    ) -> None:
        sip_hostname = None
        if _is_valid_hostname(hostname):
            sip_hostname = hostname

        sip = await self.staticipaddress_service.create_or_update(
            ip,
            lease_time,
            IpAddressType.DISCOVERED,
            subnet.id,
            created,
            created,
        )

        for interface in interfaces:
            await self.interface_service.add_ip(interface, sip)
        if sip_hostname is not None:
            node_with_hostname_exists = (
                await self.node_service.hostname_exists(sip_hostname)
            )
            if node_with_hostname_exists:
                await self.dnsresource_service.release_dynamic_hostname(sip)
            else:
                await self.dnsresource_service.update_dynamic_hostname(
                    sip, sip_hostname
                )

    async def _release_lease_info(
        self, sip: StaticIPAddress, interfaces: list[Interface], subnet: Subnet
    ) -> None:
        now = datetime.utcnow()
        if sip is None:
            sip = await self.staticipaddress_service.get_for_interfaces(
                interfaces,
                subnet=subnet,
                ip=None,
                alloc_type=IpAddressType.DISCOVERED.value,
            )

            if sip is None:
                sip = await self.staticipaddress_service.create(
                    None, 0, IpAddressType.DISCOVERED, subnet.id, now, now
                )
        else:
            await self.staticipaddress_service.update(
                sip.id,
                sip.ip,
                sip.lease_time,
                sip.alloc_type,
                sip.subnet_id,
                sip.created,
                now,
            )

        await self.interface_service.bulk_link_ip(sip, interfaces)
