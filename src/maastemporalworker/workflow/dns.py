# Copyright 2024 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Address, IPv6Address
from pathlib import Path
import re
from typing import Any, Optional

import aiodns
import aiofiles
import aiofiles.os as aiofiles_os
from netaddr import AddrFormatError, IPAddress, IPNetwork
from temporalio import activity, workflow

from maascommon.enums.dns import DnsUpdateAction
from maascommon.enums.node import NodeTypeEnum
from maascommon.enums.subnet import RdnsMode
from maascommon.workflows.dns import (
    CONFIGURE_DNS_WORKFLOW_NAME,
    ConfigureDNSParam,
    InvalidDNSUpdateError,
)
from maasservicelayer.db.filters import QuerySpec
from maasservicelayer.db.repositories.dnsdata import DNSDataClauseFactory
from maasservicelayer.db.repositories.dnsresources import (
    DNSResourceClauseFactory,
)
from maasservicelayer.db.repositories.domains import DomainsClauseFactory
from maasservicelayer.db.repositories.nodes import NodeClauseFactory
from maasservicelayer.db.repositories.subnets import SubnetClauseFactory
from maasservicelayer.models.dnsdata import DNSData
from maasservicelayer.models.dnsresources import DNSResource
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.services import ServiceCollectionV3
from maastemporalworker.workflow.activity import ActivityBase
from provisioningserver.dns.config import (
    DynamicDNSUpdate,
    get_dns_config_dir,
    get_nsupdate_key_path,
    get_rndc_conf_path,
    get_zone_file_config_dir,
)
from provisioningserver.utils import load_template

GET_CHANGES_SINCE_CURRENT_SERIAL_TIMEOUT = timedelta(minutes=5)
GET_REGION_CONTROLLERS_TIMEOUT = timedelta(minutes=5)
FULL_RELOAD_DNS_CONFIGURATION_TIMEOUT = timedelta(minutes=5)
DYNAMIC_UPDATE_DNS_CONFIGURATION_TIMEOUT = timedelta(minutes=5)
CHECK_SERIAL_UPDATE_TIMEOUT = timedelta(minutes=5)
DNS_RETRY_TIMEOUT = timedelta(minutes=5)


# Activities names
GET_CHANGES_SINCE_CURRENT_SERIAL_NAME = "get-changes-since-current-serial"
GET_REGION_CONTROLLERS_NAME = "get-region-controllers"
FULL_RELOAD_DNS_CONFIGURATION_NAME = "full-reload-dns-configuration"
DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME = "dynamic-update-dns-configuration"
CHECK_SERIAL_UPDATE_NAME = "check-serial-update"

zone_serial_regexp = re.compile(r"\s*([0-9]+)\s*\;\s*serial")


@dataclass
class DNSPublication:
    serial: int
    source: str
    update: str


@dataclass
class SerialChangesResult:
    updates: list[DynamicDNSUpdate]


@dataclass
class RegionControllersResult:
    region_controller_system_ids: list[str]


@dataclass
class DynamicUpdateParam:
    new_serial: int
    updates: list[DynamicDNSUpdate]


@dataclass
class DNSUpdateResult:
    serial: int


@dataclass
class CheckSerialUpdateParam:
    serial: int


def get_task_queue_for_update(system_id: str) -> str:
    return f"region:{system_id}"


def get_zone_config_path() -> str:
    return str(get_dns_config_dir() / Path("named.conf.maas"))


def get_zone_file_path(zone: str) -> str:
    return str(get_zone_file_config_dir() / Path(f"zone.{zone}"))


class DNSConfigActivity(ActivityBase):
    async def _get_current_serial_from_file(
        self, svc: ServiceCollectionV3
    ) -> int:
        default_domain = (
            await svc.domains.get_default_domain()
        )  # any zonefile will have the same serial
        file_path = get_zone_file_config_dir() / f"zone.{default_domain.name}"
        async with aiofiles.open(file_path, mode="r") as f:
            async for line in f:
                result = zone_serial_regexp.findall(line)
                if result:
                    return int(result[0])

    async def _dnspublication_to_dnsupdate(
        self,
        svc: ServiceCollectionV3,
        dnspublication: DNSPublication,
        default_ttl: int,
    ) -> list[DynamicDNSUpdate] | None:
        update_content = dnspublication.update.split(" ")
        ttl = default_ttl
        answer = None

        if len(update_content) == 1 and update_content[0]:
            if update_content[0] == DnsUpdateAction.RELOAD:
                return [
                    DynamicDNSUpdate(
                        operation=DnsUpdateAction.RELOAD,
                        zone="",
                        name="",
                        rectype="",
                    )
                ]
            else:
                raise InvalidDNSUpdateError(
                    f"invalid update: {dnspublication.update}"
                )
        elif len(update_content) >= 4:
            op, zone_name, rec_name, rtype = update_content[:4]
        else:
            op, zone_name, rec_name, rtype = ("", "", "", "")

        if len(update_content) > 4:
            if len(update_content) > 5:
                ttl = int(update_content[4])

            answer = update_content[-1]
            try:
                ip = IPAddress(answer)
            except AddrFormatError:
                pass
            else:
                if ip.version == 6:
                    rtype = "AAAA"

        match op:
            case DnsUpdateAction.RELOAD:
                return [
                    DynamicDNSUpdate(
                        operation=op,
                        zone=zone_name,
                        name=rec_name,
                        rectype=rtype,
                    )
                ]
            case DnsUpdateAction.INSERT:
                return [
                    DynamicDNSUpdate(
                        operation=op,
                        zone=zone_name,
                        name=rec_name,
                        rectype=rtype,
                        ttl=ttl,
                        answer=answer,
                    )
                ]
            case DnsUpdateAction.UPDATE:
                return [
                    DynamicDNSUpdate(
                        operation=DnsUpdateAction.DELETE,
                        zone=zone_name,
                        name=rec_name,
                        rectype=rtype,
                        answer=answer,
                    ),
                    DynamicDNSUpdate(
                        operation=DnsUpdateAction.INSERT,
                        zone=zone_name,
                        name=rec_name,
                        rectype=rtype,
                        ttl=ttl,
                        answer=answer,
                    ),
                ]
            case DnsUpdateAction.DELETE:
                update = DynamicDNSUpdate(
                    operation=DnsUpdateAction.DELETE,
                    zone=zone_name,
                    name=rec_name,
                    rectype=rtype,
                )
                if ttl:
                    update.ttl = ttl
                if answer:
                    update.answer = answer
                return [update]
            case DnsUpdateAction.DELETE_IP:
                updates = [
                    DynamicDNSUpdate(
                        operation=DnsUpdateAction.DELETE,
                        zone=zone_name,
                        name=rec_name,
                        rectype=rtype,
                    )
                ]
                if rtype == "A":
                    updates.append(
                        DynamicDNSUpdate(
                            operation=DnsUpdateAction.DELETE,
                            zone=zone_name,
                            name=rec_name,
                            rectype="AAAA",
                        )
                    )
                elif rtype == "AAAA":
                    updates.append(
                        DynamicDNSUpdate(
                            operation=DnsUpdateAction.DELETE,
                            zone=zone_name,
                            name=rec_name,
                            rectype="A",
                        )
                    )
                domain = await svc.domains.get_one(
                    query=QuerySpec(
                        where=DomainsClauseFactory.with_name(zone_name)
                    )
                )
                dnsrr = await svc.dnsresources.get_one(
                    query=QuerySpec(
                        where=DNSResourceClauseFactory.and_clauses(
                            [
                                DNSResourceClauseFactory.with_name(rec_name),
                                DNSResourceClauseFactory.with_domain_id(
                                    domain.id
                                ),
                            ]
                        )
                    )
                )
                remaining_ips = await svc.dnsresources.get_ips_for_dnsresource(
                    dnsrr.id
                )

                for ip in remaining_ips:
                    updates.append(
                        DynamicDNSUpdate(
                            operation=DnsUpdateAction.INSERT,
                            zone=zone_name,
                            name=rec_name,
                            rectype=(
                                "A"
                                if isinstance(ip.ip, IPv4Address)
                                else "AAAA"
                            ),
                            ttl=ttl,
                            answer=str(ip.ip),
                        )
                    )
                return updates
            case DnsUpdateAction.DELETE_IFACE_IP:
                updates = [
                    DynamicDNSUpdate(
                        operation=DnsUpdateAction.DELETE,
                        zone=zone_name,
                        name=rec_name,
                        rectype=rtype,
                    )
                ]
                if rtype == "A":
                    updates.append(
                        DynamicDNSUpdate(
                            operation=DnsUpdateAction.DELETE,
                            zone=zone_name,
                            name=rec_name,
                            rectype="AAAA",
                        )
                    )
                elif rtype == "AAAA":
                    updates.append(
                        DynamicDNSUpdate(
                            operation=DnsUpdateAction.DELETE,
                            zone=zone_name,
                            name=rec_name,
                            rectype="A",
                        )
                    )

                interface_id = int(update_content[-1])
                interface = await svc.interfaces.get_by_id(interface_id)
                ips = await svc.staticipaddress.get_for_interfaces(
                    [interface.id]
                )

                if ips:
                    for ip in ips:
                        updates.append(
                            DynamicDNSUpdate(
                                operation=DnsUpdateAction.INSERT,
                                zone=zone_name,
                                name=rec_name,
                                rectype=(
                                    "A"
                                    if isinstance(ip.ip, IPv4Address)
                                    else "AAAA"
                                ),
                                ttl=ttl,
                                answer=str(ip.ip),
                            )
                        )
                return updates

    @activity.defn(name=GET_CHANGES_SINCE_CURRENT_SERIAL_NAME)
    async def get_changes_since_current_serial(
        self,
    ) -> (int, SerialChangesResult | None):
        async with self.start_transaction() as svc:
            current_serial = await self._get_current_serial_from_file(svc)
            dnspublications = (
                await svc.dnspublications.get_publications_since_serial(
                    current_serial
                )
            )
            default_ttl = await svc.configurations.get("default_dns_ttl")

            updates = []

            for dnspublication in dnspublications:
                if update := await self._dnspublication_to_dnsupdate(
                    svc, dnspublication, default_ttl
                ):
                    updates.extend(update)

            latest_serial = (
                dnspublications[-1].serial if dnspublications else None
            )

            return latest_serial, SerialChangesResult(updates=updates)

    @activity.defn(name=GET_REGION_CONTROLLERS_NAME)
    async def get_region_controllers(self) -> RegionControllersResult:
        async with self.start_transaction() as svc:
            region_controllers = await svc.nodes.get_many(
                query=QuerySpec(
                    where=NodeClauseFactory.or_clauses(
                        [
                            NodeClauseFactory.with_type(
                                NodeTypeEnum.REGION_CONTROLLER
                            ),
                            NodeClauseFactory.with_type(
                                NodeTypeEnum.REGION_AND_RACK_CONTROLLER
                            ),
                        ],
                    )
                )
            )

        return RegionControllersResult(
            region_controller_system_ids=[
                r.system_id for r in region_controllers
            ],
        )

    def _get_ttl(
        self,
        default_ttl: int,
        domain: Domain,
        dnsrr: DNSResource,
        dnsdata: Optional[DNSData] = None,
    ) -> int:
        if dnsdata and dnsdata.ttl:
            return dnsdata.ttl
        if dnsrr.address_ttl:
            return dnsrr.address_ttl
        if domain.ttl:
            return domain.ttl
        return default_ttl

    async def _get_fwd_records(
        self, svc: ServiceCollectionV3, domains: list[Domain], default_ttl: int
    ) -> dict[str, dict[tuple[str, str], list[tuple[str, int]]]]:
        fwd_records = defaultdict(lambda: defaultdict(list))

        for domain in domains:
            dnsrrs = await svc.dnsresources.get_many(
                query=QuerySpec(
                    where=DNSResourceClauseFactory().with_domain_id(domain.id),
                )
            )
            for dnsrr in dnsrrs:
                ips = await svc.dnsresources.get_ips_for_dnsresource(dnsrr.id)
                dns_data = await svc.dnsdata.get_many(
                    query=QuerySpec(
                        where=DNSDataClauseFactory.with_dnsresource_id(
                            dnsrr.id
                        )
                    )
                )

                a_answers = [
                    (str(ip.ip), self._get_ttl(default_ttl, domain, dnsrr))
                    for ip in ips
                    if isinstance(ip.ip, IPv4Address)
                ]
                aaaa_answers = [
                    (str(ip.ip), self._get_ttl(default_ttl, domain, dnsrr))
                    for ip in ips
                    if isinstance(ip.ip, IPv6Address)
                ]

                if a_answers:
                    fwd_records[domain.name][(dnsrr.name, "A")] = a_answers

                if aaaa_answers:
                    fwd_records[domain.name][(dnsrr.name, "AAAA")] = (
                        aaaa_answers
                    )

                for dd in dns_data:
                    fwd_records[domain.name][(dnsrr.name, dd.rrtype)].append(
                        (
                            dd.rrdata,
                            self._get_ttl(
                                default_ttl, domain, dnsrr, dnsdata=dd
                            ),
                        )
                    )

        return fwd_records

    def _split_large_subnet(self, network: IPNetwork):
        new_networks = []
        first = IPAddress(network.first)
        last = IPAddress(network.last)
        if first.version == 6:
            # IPv6.
            # 2001:89ab::/19 yields 8.1.0.0.2.ip6.arpa, and the full list
            # is 8.1.0.0.2.ip6.arpa, 9.1.0.0.2.ip6.arpa
            # The ipv6 reverse dns form is 32 elements of 1 hex digit each.
            # How many elements of the reverse DNS name to we throw away?
            # Prefixlen of 0-3 gives us 1, 4-7 gives us 2, etc.
            # While this seems wrong, we always _add_ a base label back in,
            # so it's correct.
            rest_limit = (132 - network.prefixlen) // 4
            # What is the prefix for each inner subnet (It will be the next
            # smaller multiple of 4.)  If it's the smallest one, then RFC2317
            # tells us that we're adding an extra blob to the front of the
            # reverse zone name, and we want the entire prefixlen.
            subnet_prefix = (network.prefixlen + 3) // 4 * 4
            if subnet_prefix == 128:
                subnet_prefix = network.prefixlen
            # How big is the step between subnets?  Again, special case for
            # extra small subnets.
            step = 1 << ((128 - network.prefixlen) // 4 * 4)
            if step < 16:
                step = 16
            # Grab the base (hex) and trailing labels for our reverse zone.
            split_zone = first.reverse_dns.split(".")
            base = int(split_zone[rest_limit - 1], 16)
        else:
            # IPv4.
            # The logic here is the same as for IPv6, but with 8 instead of 4.
            rest_limit = (40 - network.prefixlen) // 8
            subnet_prefix = (network.prefixlen + 7) // 8 * 8
            if subnet_prefix == 32:
                subnet_prefix = network.prefixlen
            step = 1 << ((32 - network.prefixlen) // 8 * 8)
            if step < 256:
                step = 256
            # Grab the base (decimal) and trailing labels for our reverse
            # zone.
            split_zone = first.reverse_dns.split(".")
            base = int(split_zone[rest_limit - 1])

        while first <= last:
            if first > last:
                # if the excluding subnet pushes the base IP beyond the bounds of the generating subnet, we've reached the end and return early
                return new_networks

            new_networks.append(IPNetwork(f"{first}/{subnet_prefix:d}"))
            base += 1
            try:
                first += step
            except IndexError:
                # IndexError occurs when we go from 255.255.255.255 to
                # 0.0.0.0.  If we hit that, we're all fine and done.
                break
        return new_networks

    def _generate_glue_networks(
        self, subnets: list[Subnet]
    ) -> list[IPNetwork]:
        glue_nets = {}
        for subnet in subnets:
            if subnet.rdns_mode == RdnsMode.RFC2317:
                network = IPNetwork(str(subnet.cidr))
                if network.version == 4 and network.prefixlen > 24:
                    basenet = IPNetwork(
                        f"{IPNetwork(str(network.network) + '/24').network}/24"
                    ).network
                    glue_nets.setdefault(basenet, set()).add(network)
                elif network.version == 6 and network.prefixlen > 124:
                    basenet = IPNetwork(
                        f"{IPNetwork(str(network.network) + '/124').network}/124"
                    ).network
                    glue_nets.setdefault(basenet, set()).add(network)
        return glue_nets

    def _find_glue_network(
        self, network: IPNetwork, glue_nets: dict[IPAddress, set[IPNetwork]]
    ) -> set[IPNetwork]:
        glue = set()
        if (
            network.version == 6 and network.prefixlen < 124
        ) or network.prefixlen < 24:
            for net in glue_nets.copy().keys():
                if net in network:
                    glue.update(glue_nets[net])
                    del glue_nets[net]
        elif network.network in glue_nets:
            glue = glue_nets[network.network]
            del glue_nets[network.network]
        return glue

    def _get_rev_zone_name(self, network: IPNetwork) -> str:
        first = IPAddress(network.first)
        if first.version == 6:
            # IPv6.
            # 2001:89ab::/19 yields 8.1.0.0.2.ip6.arpa, and the full list
            # is 8.1.0.0.2.ip6.arpa, 9.1.0.0.2.ip6.arpa
            # The ipv6 reverse dns form is 32 elements of 1 hex digit each.
            # How many elements of the reverse DNS name to we throw away?
            # Prefixlen of 0-3 gives us 1, 4-7 gives us 2, etc.
            # While this seems wrong, we always _add_ a base label back in,
            # so it's correct.
            rest_limit = (132 - network.prefixlen) // 4
            # What is the prefix for each inner subnet (It will be the next
            # smaller multiple of 4.)  If it's the smallest one, then RFC2317
            # tells us that we're adding an extra blob to the front of the
            # reverse zone name, and we want the entire prefixlen.
            subnet_prefix = (network.prefixlen + 3) // 4 * 4
            if subnet_prefix == 128:
                subnet_prefix = network.prefixlen
            # How big is the step between subnets?  Again, special case for
            # extra small subnets.
            step = 1 << ((128 - network.prefixlen) // 4 * 4)
            if step < 16:
                step = 16
            # Grab the base (hex) and trailing labels for our reverse zone.
            split_zone = first.reverse_dns.split(".")
            zone_rest = ".".join(split_zone[rest_limit:-1])
            base = int(split_zone[rest_limit - 1], 16)
        else:
            # IPv4.
            # The logic here is the same as for IPv6, but with 8 instead of 4.
            rest_limit = (40 - network.prefixlen) // 8
            subnet_prefix = (network.prefixlen + 7) // 8 * 8
            if subnet_prefix == 32:
                subnet_prefix = network.prefixlen
            step = 1 << ((32 - network.prefixlen) // 8 * 8)
            if step < 256:
                step = 256
            # Grab the base (decimal) and trailing labels for our reverse
            # zone.
            split_zone = first.reverse_dns.split(".")
            zone_rest = ".".join(split_zone[rest_limit:-1])
            base = int(split_zone[rest_limit - 1])

        # Rest_limit has bounds of 1..labelcount+1 (5 or 33).
        # If we're stripping any elements, then we just want base.name.
        if rest_limit > 1:
            if first.version == 6:
                new_zone = f"{base:x}.{zone_rest}"
            else:
                new_zone = f"{base:d}.{zone_rest}"
        # We didn't actually strip any elemnts, so base goes back with
        # the prefixlen attached.
        elif first.version == 6:
            new_zone = f"{base:x}-{network.prefixlen:d}.{zone_rest}"
        else:
            new_zone = f"{base:d}-{network.prefixlen:d}.{zone_rest}"
        return new_zone

    async def _get_rev_records(
        self,
        svc: ServiceCollectionV3,
        subnets: list[Subnet],
        fwd_records: dict[
            str, dict[str, dict[tuple[str, str], list[tuple[str, int]]]]
        ],
    ) -> dict[str, dict[tuple[str, str], list[tuple[str, int]]]]:
        rev_records = defaultdict(lambda: defaultdict(list))
        glue_networks = self._generate_glue_networks(subnets)
        for network_pair in sorted(
            [(IPNetwork(str(subnet.cidr)), subnet) for subnet in subnets],
            key=lambda n: n[0].prefixlen,
            reverse=True,
        ):
            network, subnet = network_pair
            if subnet.rdns_mode == RdnsMode.DISABLED:
                continue
            split_networks = self._split_large_subnet(network)
            networks = [network] + split_networks
            for net in networks:
                glue = self._find_glue_network(network, glue_networks)
                for domain_name, domain_records in fwd_records.items():
                    for rec_key, answers in domain_records.items():
                        if rec_key[1] != "A" and rec_key[1] != "AAAA":
                            continue
                        if (net.version == 4 and rec_key[1] == "A") or (
                            net.version == 6 and rec_key[1] == "AAAA"
                        ):
                            rec_name = rec_key[0]
                            for answer in answers:
                                ip = IPAddress(answer[0])
                                ptr_answer = (
                                    ".".join([rec_name, domain_name]),
                                    answer[1],
                                )
                                if ip in net:
                                    in_glue = False
                                    for g in glue:
                                        if ip in g and g < net:
                                            in_glue = True
                                            glue_record = rev_records[
                                                self._get_rev_zone_name(g)
                                            ][(ip.reverse_dns, "PTR")]

                                            if ptr_answer not in glue_record:
                                                glue_record.append(ptr_answer)

                                    if not in_glue:
                                        record = rev_records[
                                            self._get_rev_zone_name(network)
                                        ][(ip.reverse_dns, "PTR")]

                                        if ptr_answer not in record:
                                            record.append(
                                                (
                                                    ".".join(
                                                        [rec_name, domain_name]
                                                    ),
                                                    answer[1],
                                                )
                                            )
        return rev_records

    def _get_rndc_conf_path(self) -> str:
        return get_rndc_conf_path()

    def _get_nsupdate_keys_path(self) -> str:
        return get_nsupdate_key_path()

    async def _rndc_cmd(self, additional: Optional[list[str]] = None) -> None:
        cmd = [
            "rndc",
            "-c",
            self._get_rndc_conf_path(),
        ]

        if additional:
            cmd += additional

        freeze = await asyncio.create_subprocess_exec(*cmd)
        ret = await freeze.wait()
        if ret != 0:
            raise Exception()  # TODO

    @asynccontextmanager
    async def _freeze(
        self, zone: Optional[str] = None, timeout: Optional[int] = 2
    ):
        freeze_args = ["freeze"]
        thaw_args = ["thaw"]
        if zone:
            freeze_args.append(zone)
            thaw_args.append(zone)

        try:
            await self._rndc_cmd(freeze_args)
            yield
        finally:
            await self._rndc_cmd(thaw_args)

    async def _write_template(
        self,
        template_name: str,
        file: aiofiles.threadpool.text.AsyncTextIOWrapper,
        **kwargs,
    ) -> None:
        tmpl = load_template("dns", template_name)
        content = tmpl.substitute(kwargs)
        await file.write(content)

    async def _write_bind_files(
        self,
        records: dict[str, dict[tuple[str, str], list[tuple[str, int]]]],
        serial: int,
        **kwargs: dict[str, Any],
    ) -> None:
        async with self._freeze():
            cfg_path = get_zone_config_path()
            zones = [(k, get_zone_file_path(k)) for k in records.keys()]
            async with aiofiles.open(f"{cfg_path}.tmp") as cfg:
                await self._write_template(
                    "named.conf.workflow.template",
                    cfg,
                    zones=zones,
                    named_rndc_conf_path=self._get_rndc_conf_path(),
                    nsupdate_keys_conf_path=self._get_nsupdate_keys_path(),
                    forwarded_zones=kwargs.get("forwarded_zones", []),
                    trusted_networks=kwargs.get("trusted_networks", []),
                )

            await aiofiles_os.rename(f"{cfg_path}.tmp", cfg_path)

            for zone_name, zone_records in records.items():
                zone_file_path = get_zone_file_path(zone_name)

                async with aiofiles.open(f"{zone_file_path}.tmp") as zf:
                    await self._write_template(
                        "zone.workflow.template",
                        zf,
                        zone_name=zone_name,
                        zone_records=zone_records,
                        zone_ttl=kwargs.get("zone_ttls", {}).get(
                            zone_name, 30
                        ),
                        ns_ttl=kwargs.get("ns_ttls", {}).get(
                            zone_name,
                            kwargs.get("zone_ttls", {}).get(zone_name, 30),
                        ),
                        ns_host_name=kwargs.get("ns_host_name"),
                        serial=serial,
                        modified=kwargs.get(
                            "modified", datetime.now(timezone.utc)
                        ),
                    )

                await aiofiles_os.rename(
                    f"{zone_file_path}.tmp", zone_file_path
                )

    @activity.defn(name=FULL_RELOAD_DNS_CONFIGURATION_NAME)
    async def full_reload_dns_configuration(self) -> DNSUpdateResult:
        async with self.start_transaction() as svc:
            domains = await svc.domains.get_many(
                query=QuerySpec(
                    where=DomainsClauseFactory.with_authoritative(True),
                )
            )
            default_domain = await svc.domains.get_default_domain()
            subnets = await svc.subnets.get_many(
                query=QuerySpec(
                    where=SubnetClauseFactory.with_not_rdns_mode(
                        RdnsMode.DISABLED
                    )
                )
            )
            trusted_networks = await svc.subnets.get_many(
                query=QuerySpec(
                    where=SubnetClauseFactory.with_allow_dns(True),
                )
            )
            default_ttl = await svc.configurations.get("default_dns_ttl")
            serial = await svc.dnspublications.get_latest_serial()

            forwarded_domains = await svc.domains.get_forwarded_domains()
            fwd_records = await self._get_fwd_records(
                svc,
                domains,
                default_ttl,
            )
            rev_records = await self._get_rev_records(
                svc,
                subnets,
                fwd_records,
            )

            records = {}
            records.update(fwd_records)
            records.update(rev_records)
            zone_ttls = {
                domain.name: domain.ttl if domain.ttl else default_ttl
                for domain in domains
            }
            ns_ttls = {
                zone_name: record_answer[1]
                for zone_name, records in fwd_records.items()
                for record_key, record_answer in records.items()
                if record_key[1] == "NS"
            }
            for domain in domains:
                if domain.name not in ns_ttls:
                    ns_ttls[domain.name] = (
                        domain.ttl if domain.ttl else default_ttl
                    )

            await self._write_bind_files(
                records,
                serial,
                fowarded_zones=[
                    (
                        domain.name,
                        (srvr.ip_address, srvr.port),
                    )
                    for domain, srvr in forwarded_domains
                ],
                trusted_networks=[
                    str(subnet.cidr) for subnet in trusted_networks
                ],
                zone_ttls=zone_ttls,
                ns_ttls=ns_ttls,
                ns_host_name=default_domain.name,
            )
        return DNSUpdateResult(serial=serial)

    async def _nsupdate(
        self,
        updates: list[DynamicDNSUpdate],
        domains: list[Domain],
        subnets: list[Subnet],
        serial: int,
        server_address: Optional[str] = None,
        default_ttl: Optional[int] = 30,
    ) -> None:
        stdin = []

        def _fwd_updates(domain: Domain) -> list[str]:
            ttl = domain.ttl if domain.ttl else default_ttl
            return (
                [f"zone {domain.name}"]
                + [
                    self._format_update(update)
                    for update in updates
                    if update.zone == domain.name
                ]
                + [
                    f"update add {domain.name} {ttl} SOA {domain.name}. nobody.example.com. {serial} 600 1800 604800 {ttl}"
                ]
            )

        def _rev_updates(subnet: Subnet) -> list[str]:
            network = IPNetwork(str(subnet.cidr))
            zone_name = self._get_rev_zone_name(network)
            return (
                [f"zone {zone_name}"]
                + [
                    self._format_update(DynamicDNSUpdate.as_rev_record(update))
                    for update in updates
                    if update.ip and update.ip in network
                ]
                + [
                    f"update add {zone_name} {default_ttl} SOA {zone_name}. nobody.example.com. {serial} 600 1800 604800 {default_ttl}"
                ]
            )

        for domain in domains:
            stdin += _fwd_updates(domain)

        for subnet in subnets:
            stdin += _rev_updates(subnet)

        stdin += ["send\n"]

        if server_address:
            stdin = [f"server {server_address}"] + stdin

        cmd = ["nsupdate", "-k", self._get_nsupdate_keys_path()]
        if len(updates) > 1:
            cmd.append("-v")  # use TCP for bulk updates

        proc = await asyncio.create_subprocess_exec(
            *cmd, stdin=asyncio.subprocess.PIPE
        )
        await proc.communicate(input="\n".join(stdin).encode("ascii"))

    def _format_update(self, update):
        if update.operation == "DELETE":
            if update.answer:
                return f"update delete {update.name} {update.rectype} {update.answer}"
            return f"update delete {update.name} {update.rectype}"
        ttl = update.ttl
        return (
            f"update add {update.name} {ttl} {update.rectype} {update.answer}"
        )

    @activity.defn(name=DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME)
    async def dynamic_update_dns_configuration(
        self, updates: DynamicUpdateParam
    ) -> DNSUpdateResult:
        async with self.start_transaction() as svc:
            domains = await svc.domains.get_many(
                query=QuerySpec(
                    where=DomainsClauseFactory.with_authoritative(True),
                ),
            )
            subnets = await svc.subnets.get_many(
                query=QuerySpec(
                    where=SubnetClauseFactory.with_not_rdns_mode(
                        RdnsMode.DISABLED
                    ),
                ),
            )
            default_ttl = await svc.configurations.get("default_dns_ttl")

            await self._nsupdate(
                updates.updates,
                domains,
                subnets,
                updates.new_serial,
                default_ttl,
            )

        return DNSUpdateResult(serial=updates.new_serial)

    def _get_resolver(self) -> aiodns.DNSResolver:
        loop = asyncio.get_event_loop()
        return aiodns.DNSResolver(loop=loop)

    @activity.defn(name=CHECK_SERIAL_UPDATE_NAME)
    async def check_serial_update(
        self, serial: CheckSerialUpdateParam
    ) -> None:
        resolver = self._get_resolver()

        domain = None

        async with self.start_transaction() as svc:
            domain = await svc.domains.get_default_domain()

        soa = await resolver.query(domain.name, "SOA")

        assert soa.serial == serial.serial


@workflow.defn(name=CONFIGURE_DNS_WORKFLOW_NAME, sandboxed=False)
class ConfigureDNSWorkflow:
    @workflow.run
    async def run(self, param: ConfigureDNSParam) -> None:
        updates = None
        need_full_reload = param.need_full_reload

        if not need_full_reload:
            latest_serial, updates = await workflow.execute_activity(
                GET_CHANGES_SINCE_CURRENT_SERIAL_NAME,
                start_to_close_timeout=GET_CHANGES_SINCE_CURRENT_SERIAL_TIMEOUT,
            )
            if latest_serial is None:
                return

            for publication in updates["updates"]:
                if publication["operation"] == DnsUpdateAction.RELOAD:
                    need_full_reload = True

        region_controllers = await workflow.execute_activity(
            GET_REGION_CONTROLLERS_NAME,
            start_to_close_timeout=GET_REGION_CONTROLLERS_TIMEOUT,
        )

        for region_controller_system_id in region_controllers[
            "region_controller_system_ids"
        ]:
            if need_full_reload:
                new_serial = await workflow.execute_activity(
                    FULL_RELOAD_DNS_CONFIGURATION_NAME,
                    start_to_close_timeout=FULL_RELOAD_DNS_CONFIGURATION_TIMEOUT,
                    task_queue=get_task_queue_for_update(
                        region_controller_system_id
                    ),
                )

            elif updates["updates"]:
                new_serial = await workflow.execute_activity(
                    DYNAMIC_UPDATE_DNS_CONFIGURATION_NAME,
                    DynamicUpdateParam(
                        new_serial=latest_serial,
                        updates=[DynamicDNSUpdate(**updates["updates"][-1])],
                    ),
                    start_to_close_timeout=DYNAMIC_UPDATE_DNS_CONFIGURATION_TIMEOUT,
                    task_queue=get_task_queue_for_update(
                        region_controller_system_id
                    ),
                )

            await workflow.execute_activity(
                CHECK_SERIAL_UPDATE_NAME,
                CheckSerialUpdateParam(serial=new_serial["serial"]),
                start_to_close_timeout=CHECK_SERIAL_UPDATE_TIMEOUT,
                task_queue=get_task_queue_for_update(
                    region_controller_system_id
                ),
            )
