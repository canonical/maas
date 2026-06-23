from datetime import datetime, timezone
from typing import Any, cast
from unittest.mock import AsyncMock, Mock

from netaddr import IPNetwork
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection
from temporalio.client import Client
from temporalio.testing import ActivityEnvironment

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maasservicelayer.db import Database
from maasservicelayer.services import CacheForServices
from maastemporalworker.workflow.dhcp import (
    ConfigureDHCPParam,
    DHCPConfigActivity,
    DHCPDataForAgent,
    FetchHostsForUpdateParam,
    GetActiveInterfacesForAgentParam,
    GetDHCPDataForAgentParam,
    Host,
    HostReservationData,
    InterfaceData,
    IPRangeData,
    SubnetData,
    VlanData,
)
from provisioningserver.boot import BootMethod
from tests.fixtures.factories.configuration import create_test_configuration
from tests.fixtures.factories.interface import create_test_interface_entry
from tests.fixtures.factories.iprange import create_test_ip_range_entry
from tests.fixtures.factories.node import (
    create_test_machine_entry,
    create_test_rack_controller_entry,
)
from tests.fixtures.factories.reserved_ips import create_test_reserved_ip_entry
from tests.fixtures.factories.secret import create_test_secret
from tests.fixtures.factories.staticipaddress import (
    create_test_staticipaddress_entry,
)
from tests.fixtures.factories.subnet import create_test_subnet_entry
from tests.fixtures.factories.vlan import create_test_vlan_entry
from tests.maasapiserver.fixtures.db import Fixture


class _FakeBootMethod:
    def __init__(
        self,
        name: str,
        *,
        arch_octet: str | list[str] | None = None,
        user_class: str | None = None,
        bootloader_path: str = "bootloader",
        path_prefix: str | None = None,
        path_prefix_http: bool = False,
        path_prefix_force: bool = False,
        http_url: bool = False,
        absolute_url_as_filename: bool = False,
    ) -> None:
        self.name = name
        self.arch_octet = arch_octet
        self.user_class = user_class
        self.bootloader_path = bootloader_path
        self.path_prefix = path_prefix
        self.path_prefix_http = path_prefix_http
        self.path_prefix_force = path_prefix_force
        self.http_url = http_url
        self.absolute_url_as_filename = absolute_url_as_filename


def FakeBootMethod(name: str, **kwargs: Any) -> BootMethod:
    return cast(BootMethod, _FakeBootMethod(name, **kwargs))


@pytest.mark.asyncio
class TestDHCPConfigActivity:
    async def test_get_agents_for_vlans(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        rack_controller1 = await create_test_rack_controller_entry(fixture)
        rack_controller2 = await create_test_rack_controller_entry(fixture)
        rack_controller3 = await create_test_rack_controller_entry(fixture)

        vlan = await create_test_vlan_entry(
            fixture,
            primary_rack_id=rack_controller1["id"],
            secondary_rack_id=rack_controller2["id"],
            dhcp_on=True,
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_agents_for_vlans(
            db_connection, {vlan["id"]}
        )

        assert rack_controller3["system_id"] not in result

        assert result == {
            rack_controller1["system_id"],
            rack_controller2["system_id"],
        }

    async def test_get_vlans_for_subnet(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
            for _ in range(3)
        ]

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_vlans_for_subnets(
            db_connection, [s["id"] for s in subnets]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_get_vlans_for_ip_ranges(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
        ]
        ip_ranges = [
            await create_test_ip_range_entry(fixture, subnet=subnet)
            for subnet in subnets
        ]

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_vlans_for_ip_ranges(
            db_connection, [ip_range["id"] for ip_range in ip_ranges]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_get_vlans_for_static_ip_addrs(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
        ]
        ips = [
            (
                await create_test_staticipaddress_entry(
                    fixture, subnet_id=subnet["id"]
                )
            )[0]
            for subnet in subnets
            for _ in range(3)
        ]

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_vlans_for_static_ip_addrs(
            db_connection, [ip["id"] for ip in ips]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_get_vlans_for_reserved_ips(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlans = [
            await create_test_vlan_entry(fixture, dhcp_on=True)
            for _ in range(3)
        ]
        subnets = [
            await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
            for vlan in vlans
        ]
        reserved_ips = [
            await create_test_reserved_ip_entry(fixture, subnet=subnet)
            for subnet in subnets
        ]

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_vlans_for_reserved_ips(
            db_connection, [ip["id"] for ip in reserved_ips]
        )
        assert result == {vlan["id"] for vlan in vlans}

    async def test_find_agents_for_update(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        rack_controller1 = await create_test_rack_controller_entry(fixture)
        rack_controller2 = await create_test_rack_controller_entry(fixture)
        rack_controller3 = await create_test_rack_controller_entry(fixture)

        vlan1 = await create_test_vlan_entry(
            fixture,
            primary_rack_id=rack_controller1["id"],
            dhcp_on=True,
        )
        vlan2 = await create_test_vlan_entry(
            fixture,
            primary_rack_id=rack_controller3["id"],
            dhcp_on=True,
        )

        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan2["id"])

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await env.run(
            activities.find_agents_for_updates,
            ConfigureDHCPParam(
                system_ids=[rack_controller2["system_id"]],
                vlan_ids=[vlan1["id"]],
                subnet_ids=[subnet["id"]],
                static_ip_addr_ids=[],
                ip_range_ids=[],
                reserved_ip_ids=[],
            ),
        )

        for rc in [rack_controller1, rack_controller2, rack_controller3]:
            assert rc["system_id"] in result.agent_system_ids

    async def test_get_hosts_for_static_ip_addrs(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        rack = await create_test_rack_controller_entry(fixture)
        vlan = await create_test_vlan_entry(
            fixture, dhcp_on=True, primary_rack_id=rack["id"]
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        ips = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        machine = await create_test_machine_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=machine, ips=ips, vlan_id=vlan["id"]
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_hosts_for_static_ip_addresses(
            db_connection, rack["system_id"], [ip["id"] for ip in ips]
        )
        assert result == [
            Host(
                ip=str(ip["ip"]),
                mac=interface.mac_address,
                hostname=machine["hostname"],
            )
            for ip in ips
        ]

    async def test_get_hosts_for_reserved_ips(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        rack = await create_test_rack_controller_entry(fixture)
        vlan = await create_test_vlan_entry(
            fixture, dhcp_on=True, primary_rack_id=rack["id"]
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        reserved_ip = await create_test_reserved_ip_entry(
            fixture, subnet=subnet
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await activities._get_hosts_for_reserved_ips(
            db_connection, rack["system_id"], [reserved_ip["id"]]
        )
        assert result == [
            Host(
                ip=str(reserved_ip["ip"]),
                mac=reserved_ip["mac_address"],
                hostname="",
            )
        ]

    async def test_fetch_hosts_for_update(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        rack = await create_test_rack_controller_entry(fixture)
        vlan = await create_test_vlan_entry(
            fixture, dhcp_on=True, primary_rack_id=rack["id"]
        )
        subnet = await create_test_subnet_entry(fixture, vlan_id=vlan["id"])
        ips = await create_test_staticipaddress_entry(fixture, subnet=subnet)
        machine = await create_test_machine_entry(fixture)
        interface = await create_test_interface_entry(
            fixture, node=machine, ips=ips, vlan_id=vlan["id"]
        )
        reserved_ip = await create_test_reserved_ip_entry(
            fixture, subnet=subnet
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await env.run(
            activities.fetch_hosts_for_update,
            FetchHostsForUpdateParam(
                system_id=rack["system_id"],
                static_ip_addr_ids=[ip["id"] for ip in ips],
                reserved_ip_ids=[reserved_ip["id"]],
            ),
        )
        for host in [
            Host(
                ip=str(ip["ip"]),
                mac=interface.mac_address,
                hostname=machine["hostname"],
            )
            for ip in ips
        ] + [
            Host(
                ip=str(reserved_ip["ip"]),
                mac=reserved_ip["mac_address"],
                hostname="",
            )
        ]:
            assert host in result.hosts

    async def test_get_omapi_key(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        key = await create_test_secret(
            fixture, path="global/omapi-key", value={"secret": "abc"}
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await env.run(activities.get_omapi_key)

        assert result.key == key.value["secret"]

    async def test_get_active_interfaces_for_agent(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        rack_controller = await create_test_rack_controller_entry(fixture)
        vlan1 = await create_test_vlan_entry(fixture, dhcp_on=True)
        vlan2 = await create_test_vlan_entry(fixture, dhcp_on=False)
        iface1 = await create_test_interface_entry(
            fixture, vlan=vlan1, node=rack_controller
        )
        await create_test_interface_entry(
            fixture, vlan=vlan2, node=rack_controller
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await env.run(
            activities.get_active_interfaces_for_agent,
            GetActiveInterfacesForAgentParam(
                system_id=rack_controller["system_id"]
            ),
        )

        assert result.ifaces == [iface1.name]

    async def test_get_dhcp_data_for_agent(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        env = ActivityEnvironment()

        await create_test_configuration(
            fixture, name="use_external_ntp_only", value=False
        )
        rack_controller = await create_test_rack_controller_entry(fixture)
        vlan1 = await create_test_vlan_entry(fixture, dhcp_on=True)
        vlan2 = await create_test_vlan_entry(fixture, dhcp_on=False)
        subnet1 = await create_test_subnet_entry(
            fixture,
            vlan_id=vlan1["id"],
            gateway_ip="10.2.3.4",
            dns_servers=["10.6.7.8"],
            cidr=IPNetwork("10.2.3.0/24"),
        )
        await create_test_subnet_entry(fixture, vlan_id=vlan2["id"])
        iprange = await create_test_ip_range_entry(
            fixture, subnet=subnet1, offset=1, size=5, type=IPRangeType.DYNAMIC
        )
        sips = await create_test_staticipaddress_entry(
            fixture, subnet=subnet1, alloc_type=IpAddressType.STICKY
        )
        iface1 = await create_test_interface_entry(
            fixture,
            vlan=vlan1,
            node=rack_controller,
            ips=sips,
        )
        await create_test_interface_entry(
            fixture, vlan=vlan2, node=rack_controller
        )
        host = await create_test_machine_entry(fixture)
        host_sips = await create_test_staticipaddress_entry(
            fixture,
            subnet=subnet1,
            alloc_type=IpAddressType.AUTO,
        )
        host_interface = await create_test_interface_entry(
            fixture,
            vlan=vlan1,
            node=host,
            ips=host_sips,
        )

        services_cache = CacheForServices()
        activities = DHCPConfigActivity(
            db,
            services_cache,
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        result = await env.run(
            activities.get_dhcp_data_for_agent,
            GetDHCPDataForAgentParam(
                system_id=rack_controller["system_id"],
            ),
        )

        assert result == DHCPDataForAgent(
            vlans=[
                VlanData(
                    id=vlan1["id"],
                    vid=vlan1["vid"],
                    relayed_vlan_id=vlan1["relay_vlan_id"],
                    mtu=vlan1["mtu"],
                )
            ],
            subnets=[
                SubnetData(
                    id=subnet1["id"],
                    ip_version=4,
                    cidr=str(subnet1["cidr"]),
                    gateway_ip=str(subnet1["gateway_ip"]),
                    dns_servers=["127.0.0.1"] + subnet1["dns_servers"],
                    allow_dns=subnet1["allow_dns"],
                    vlan_id=subnet1["vlan_id"],
                    vlan_mtu=vlan1["mtu"],
                    mask=str(subnet1["cidr"].netmask),
                    broadcast_ip=str(subnet1["cidr"].broadcast_address),
                    domain_name="maas",
                    search_list=["maas"],
                    ntp_servers=[str(sips[0]["ip"])],
                    next_server=str(sips[0]["ip"]),
                    pools=[
                        IPRangeData(
                            id=iprange["id"],
                            start_ip=str(iprange["start_ip"]),
                            end_ip=str(iprange["end_ip"]),
                            dynamic=iprange["type"] == IPRangeType.DYNAMIC,
                            subnet_id=iprange["subnet_id"],
                        )
                    ],
                    host_reservations=[
                        HostReservationData(
                            ip=str(sips[0]["ip"]),
                            mac_address=iface1.mac_address,  # type: ignore
                            hostname=rack_controller["hostname"]
                            + "-"
                            + iface1.name,
                        ),
                        HostReservationData(
                            ip=str(host_sips[0]["ip"]),
                            mac_address=str(host_interface.mac_address),
                            hostname=host["hostname"]
                            + "-"
                            + host_interface.name,
                        ),
                    ],
                )
            ],
            ipranges=[
                IPRangeData(
                    id=iprange["id"],
                    start_ip=str(iprange["start_ip"]),
                    end_ip=str(iprange["end_ip"]),
                    dynamic=iprange["type"] == IPRangeType.DYNAMIC,
                    subnet_id=iprange["subnet_id"],
                )
            ],
            interfaces=[
                InterfaceData(
                    id=iface1.id,
                    name=iface1.name,
                    vlan_id=iface1.vlan_id,  # type: ignore
                )
            ],
            default_dns_servers=[str(sip["ip"]) for sip in sips],
            ntp_servers=[str(sip["ip"]) for sip in sips],
        )

    async def test_get_dhcp_host_reservations(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlan = await create_test_vlan_entry(fixture, dhcp_on=True)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan["id"], cidr=IPNetwork("10.2.3.0/24")
        )
        machine = await create_test_machine_entry(fixture)
        host_sips = await create_test_staticipaddress_entry(
            fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
        )
        host_interface = await create_test_interface_entry(
            fixture, vlan=vlan, node=machine, ips=host_sips
        )
        # Shares a MAC with host_interface, so it must be deduplicated.
        await create_test_reserved_ip_entry(
            fixture,
            subnet=subnet,
            mac_address=str(host_interface.mac_address),
        )
        reserved_ip = await create_test_reserved_ip_entry(
            fixture, subnet=subnet, mac_address="02:03:04:05:06:07"
        )

        activities = DHCPConfigActivity(
            db,
            CacheForServices(),
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        async with activities.start_transaction() as svc:
            result = await activities.get_dhcp_host_reservations(
                svc, subnet["id"]
            )

        assert result == [
            HostReservationData(
                ip=str(host_sips[0]["ip"]),
                mac_address=str(host_interface.mac_address),
                hostname=f"{machine['hostname']}-{host_interface.name}",
            ),
            HostReservationData(
                ip=str(reserved_ip["ip"]),
                mac_address=reserved_ip["mac_address"],
                hostname=f"rsvd-{reserved_ip['id']}",
            ),
        ]

    async def test_get_dhcp_host_reservations_bond_uses_parents(
        self, fixture: Fixture, db_connection: AsyncConnection, db: Database
    ) -> None:
        vlan = await create_test_vlan_entry(fixture, dhcp_on=True)
        subnet = await create_test_subnet_entry(
            fixture, vlan_id=vlan["id"], cidr=IPNetwork("10.2.3.0/24")
        )
        machine = await create_test_machine_entry(fixture)
        bond_sips = await create_test_staticipaddress_entry(
            fixture, subnet=subnet, alloc_type=IpAddressType.AUTO
        )
        bond = await create_test_interface_entry(
            fixture,
            vlan=vlan,
            node=machine,
            ips=bond_sips,
            name="bond0",
            type=InterfaceType.BOND,
            mac_address="02:00:00:00:00:00",
        )
        parent1 = await create_test_interface_entry(
            fixture,
            vlan=vlan,
            node=machine,
            name="eth0",
            mac_address="02:00:00:00:00:01",
        )
        parent2 = await create_test_interface_entry(
            fixture,
            vlan=vlan,
            node=machine,
            name="eth1",
            mac_address="02:00:00:00:00:02",
        )
        now = datetime.now(timezone.utc).astimezone()
        await fixture.create(
            "maasserver_interfacerelationship",
            [
                {
                    "created": now,
                    "updated": now,
                    "child_id": bond.id,
                    "parent_id": parent1.id,
                },
                {
                    "created": now,
                    "updated": now,
                    "child_id": bond.id,
                    "parent_id": parent2.id,
                },
            ],
        )

        activities = DHCPConfigActivity(
            db,
            CacheForServices(),
            temporal_client=Mock(Client),
            connection=db_connection,
        )

        async with activities.start_transaction() as svc:
            result = await activities.get_dhcp_host_reservations(
                svc, subnet["id"]
            )

        assert result == [
            HostReservationData(
                ip=str(bond_sips[0]["ip"]),
                mac_address=str(parent1.mac_address),
                hostname=f"{machine['hostname']}-{parent1.name}",
            ),
            HostReservationData(
                ip=str(bond_sips[0]["ip"]),
                mac_address=str(parent2.mac_address),
                hostname=f"{machine['hostname']}-{parent2.name}",
            ),
        ]

    def _make_activity(self, db: Database) -> DHCPConfigActivity:
        return DHCPConfigActivity(
            db,
            CacheForServices(),
            temporal_client=Mock(Client),
            connection=Mock(AsyncConnection),
        )

    async def test_make_interface_hostname_without_node_config(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        interface = Mock(id=42, node_config_id=None)
        interface.name = "eth0.10"
        svc = Mock()

        hostname = await activities._make_interface_hostname(interface, svc)

        assert hostname == "unknown-42-eth0-10"

    async def test_make_interface_hostname_with_node_config(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        interface = Mock(id=42, node_config_id=5)
        interface.name = "eth0.10"
        svc = Mock()
        node = Mock()
        node.hostname = "my-host"
        svc.nodes.get_one = AsyncMock(return_value=node)

        hostname = await activities._make_interface_hostname(interface, svc)

        assert hostname == "my-host-eth0-10"

    async def test_get_kea_shared_networks_config_ipv4(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        data = DHCPDataForAgent(
            vlans=[],
            subnets=[
                SubnetData(
                    id=1,
                    ip_version=4,
                    cidr="10.0.0.0/24",
                    gateway_ip="10.0.0.1",
                    dns_servers=["10.0.0.2", "10.0.0.3"],
                    allow_dns=True,
                    vlan_id=10,
                    vlan_mtu=1500,
                    mask="255.255.255.0",
                    broadcast_ip="10.0.0.255",
                    domain_name="maas",
                    search_list=["maas", "example.com"],
                    ntp_servers=["10.0.0.5"],
                    next_server="10.0.0.7",
                    pools=[
                        IPRangeData(
                            id=1,
                            subnet_id=1,
                            dynamic=True,
                            start_ip="10.0.0.10",
                            end_ip="10.0.0.20",
                        )
                    ],
                    host_reservations=[
                        HostReservationData(
                            ip="10.0.0.30",
                            mac_address="00:55:44:11:22:33",
                            hostname="host-name",
                        )
                    ],
                )
            ],
            ipranges=[],
            interfaces=[],
            default_dns_servers=[],
            ntp_servers=[],
        )

        result = await activities.get_kea_shared_networks_config_ipv4(
            data, rack_ip="10.0.0.1"
        )

        assert result == {
            "shared-networks": [
                {
                    "name": "vlan-10",
                    "subnet4": [
                        {
                            "subnet": "10.0.0.0/24",
                            "match-client-id": False,
                            "pools": [{"pool": "10.0.0.10 - 10.0.0.20"}],
                            "reservations": [
                                {
                                    "hw-address": data.subnets[0]
                                    .host_reservations[0]
                                    .mac_address,
                                    "ip-address": data.subnets[0]
                                    .host_reservations[0]
                                    .ip,
                                    "hostname": data.subnets[0]
                                    .host_reservations[0]
                                    .hostname,
                                }
                            ],
                            "option-data": [
                                {
                                    "name": "subnet-mask",
                                    "data": "255.255.255.0",
                                },
                                {
                                    "name": "broadcast-address",
                                    "data": "10.0.0.255",
                                },
                                {"name": "domain-name", "data": "maas"},
                                {
                                    "name": "domain-name-servers",
                                    "data": "10.0.0.2, 10.0.0.3",
                                },
                                {
                                    "name": "domain-search",
                                    "data": "maas, example.com",
                                },
                                {"name": "routers", "data": "10.0.0.1"},
                                {
                                    "name": "ntp-servers",
                                    "data": "10.0.0.5",
                                },
                            ],
                            "next-server": "10.0.0.7",
                        }
                    ],
                }
            ]
        }

    async def test_get_kea_shared_networks_config_ipv4_minimal(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        data = DHCPDataForAgent(
            vlans=[],
            subnets=[
                SubnetData(
                    id=1,
                    ip_version=4,
                    cidr="10.0.0.0/24",
                    gateway_ip="",
                    dns_servers=None,
                    allow_dns=True,
                    vlan_id=10,
                    vlan_mtu=1500,
                    mask="255.255.255.0",
                    broadcast_ip="10.0.0.255",
                    domain_name="maas",
                    search_list=None,
                    ntp_servers=None,
                    next_server="",
                    pools=[],
                    host_reservations=[],
                )
            ],
            ipranges=[],
            interfaces=[],
            default_dns_servers=[],
            ntp_servers=[],
        )

        result = await activities.get_kea_shared_networks_config_ipv4(
            data, rack_ip="10.0.0.1"
        )

        assert result == {
            "shared-networks": [
                {
                    "name": "vlan-10",
                    "subnet4": [
                        {
                            "subnet": "10.0.0.0/24",
                            "match-client-id": False,
                            "pools": [],
                            "reservations": [],
                            "option-data": [
                                {
                                    "name": "subnet-mask",
                                    "data": "255.255.255.0",
                                },
                                {
                                    "name": "broadcast-address",
                                    "data": "10.0.0.255",
                                },
                                {"name": "domain-name", "data": "maas"},
                            ],
                        }
                    ],
                }
            ]
        }

    async def test_get_kea_shared_networks_config_ipv4_groups_by_vlan(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)

        def make_subnet(subnet_id: int, vlan_id: int, cidr: str) -> SubnetData:
            return SubnetData(
                id=subnet_id,
                ip_version=4,
                cidr=cidr,
                gateway_ip="",
                dns_servers=None,
                allow_dns=True,
                vlan_id=vlan_id,
                vlan_mtu=1500,
                mask="255.255.255.0",
                broadcast_ip="",
                domain_name="maas",
                search_list=None,
                ntp_servers=None,
                next_server="",
                pools=[],
                host_reservations=[],
            )

        data = DHCPDataForAgent(
            vlans=[],
            subnets=[
                make_subnet(1, 10, "10.0.0.0/24"),
                make_subnet(2, 10, "10.0.1.0/24"),
                make_subnet(3, 20, "10.0.2.0/24"),
            ],
            ipranges=[],
            interfaces=[],
            default_dns_servers=[],
            ntp_servers=[],
        )

        result = await activities.get_kea_shared_networks_config_ipv4(
            data, rack_ip="10.0.0.1"
        )

        networks = result["shared-networks"]
        assert [n["name"] for n in networks] == ["vlan-10", "vlan-20"]
        assert [s["subnet"] for s in networks[0]["subnet4"]] == [
            "10.0.0.0/24",
            "10.0.1.0/24",
        ]
        assert [s["subnet"] for s in networks[1]["subnet4"]] == ["10.0.2.0/24"]

    async def test_get_kea_shared_networks_config_ipv6(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        data = DHCPDataForAgent(
            vlans=[],
            subnets=[
                SubnetData(
                    id=1,
                    ip_version=6,
                    cidr="2001:db8::/64",
                    gateway_ip="2001:db8::1",
                    dns_servers=["2001:db8::2"],
                    allow_dns=True,
                    vlan_id=20,
                    vlan_mtu=1500,
                    mask="",
                    broadcast_ip="",
                    domain_name="maas",
                    search_list=["maas"],
                    ntp_servers=["2001:db8::5"],
                    next_server="2001:db8::7",
                    pools=[
                        IPRangeData(
                            id=1,
                            subnet_id=1,
                            dynamic=True,
                            start_ip="2001:db8::10",
                            end_ip="2001:db8::20",
                        )
                    ],
                    host_reservations=[
                        HostReservationData(
                            ip="2001:db8::30",
                            mac_address="00:55:44:11:22:33",
                            hostname="host-name",
                        )
                    ],
                )
            ],
            ipranges=[],
            interfaces=[],
            default_dns_servers=[],
            ntp_servers=[],
        )

        result = await activities.get_kea_shared_networks_config_ipv6(
            data, rack_ip="2001:db8::1"
        )

        assert result == {
            "shared-networks": [
                {
                    "name": "vlan-20",
                    "subnet6": [
                        {
                            "subnet": "2001:db8::/64",
                            "match-client-id": False,
                            "pools": [{"pool": "2001:db8::10 - 2001:db8::20"}],
                            "option-data": [
                                {"name": "domain-name", "data": "maas"},
                                {
                                    "name": "dns-servers",
                                    "data": "2001:db8::2",
                                },
                                {"name": "domain-search", "data": "maas"},
                                {
                                    "name": "ntp-servers",
                                    "data": "2001:db8::5",
                                },
                            ],
                            "reservations": [
                                {
                                    "hw-address": data.subnets[0]
                                    .host_reservations[0]
                                    .mac_address,
                                    "ip-address": data.subnets[0]
                                    .host_reservations[0]
                                    .ip,
                                    "hostname": data.subnets[0]
                                    .host_reservations[0]
                                    .hostname,
                                }
                            ],
                            "next-server": "2001:db8::7",
                        }
                    ],
                }
            ]
        }

    async def test_get_kea_run_scripts_hook_config_deb(
        self, db: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MAAS_PATH", raising=False)
        activities = self._make_activity(db)

        result = activities._get_kea_run_scripts_hook_config()

        assert result == {
            "library": "libdhcp_run_script.so",
            "parameters": {
                "name": "/usr/sbin/maas-kea-dhcp-helper",
                "sync": False,
            },
        }

    async def test_get_kea_run_scripts_hook_config_snap(
        self, db: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAAS_PATH", "/snap/maas/current")
        activities = self._make_activity(db)

        result = activities._get_kea_run_scripts_hook_config()

        assert result == {
            "library": "libdhcp_run_script.so",
            "parameters": {
                "name": "/snap/maas/current/usr/sbin/maas-kea-dhcp-helper",
                "sync": False,
            },
        }

    async def test_get_kea_hooks_libraries_deb(
        self, db: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MAAS_PATH", raising=False)
        activities = self._make_activity(db)

        result = activities.get_kea_hooks_libraries()

        assert result == {
            "hooks-libraries": [
                {
                    "library": "libdhcp_run_script.so",
                    "parameters": {
                        "name": "/usr/sbin/maas-kea-dhcp-helper",
                        "sync": False,
                    },
                }
            ]
        }

    async def test_get_kea_hooks_libraries_snap(
        self, db: Database, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MAAS_PATH", "/snap/maas/current")
        activities = self._make_activity(db)

        result = activities.get_kea_hooks_libraries()

        assert result == {
            "hooks-libraries": [
                {
                    "library": "libdhcp_run_script.so",
                    "parameters": {
                        "name": "/snap/maas/current/usr/sbin/maas-kea-dhcp-helper",
                        "sync": False,
                    },
                }
            ]
        }

    async def test_get_kea_bootloaders_only_default_fallback_ipv4(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)

        result = await activities.get_kea_bootloaders_client_classes(
            [], "10.0.0.1", ipv6=False
        )

        assert result == [
            {
                "name": "fallback-pxe",
                "test": "not ()",
                "option-data": [
                    {
                        "name": "path-prefix",
                        "data": "http://10.0.0.1:5248/",
                        "always-send": True,
                    }
                ],
                "boot-file-name": "lpxelinux.0",
            }
        ]

    async def test_get_kea_bootloaders_only_default_fallback_ipv6(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)

        result = await activities.get_kea_bootloaders_client_classes(
            [], "fe80::1", ipv6=True
        )

        assert result == [
            {
                "name": "fallback-uefi_amd64_tftp",
                "test": "not ()",
                "option-data": [
                    {
                        "name": "bootfile-url",
                        "data": "tftp://[fe80::1]/bootx64.efi",
                    }
                ],
            }
        ]

    async def test_get_kea_bootloaders_arch_octet_string_ipv4(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "uefi_amd64", arch_octet="00:07", bootloader_path="bootx64.efi"
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert result[0] == {
            "name": "boot-uefi_amd64",
            "test": "option[93].hex == '0x07'",
            "boot-file-name": "bootx64.efi",
            "option-data": [],
        }
        assert result[1]["test"] == "not ((option[93].hex == '0x07'))"

    async def test_get_kea_bootloaders_arch_octet_list_ipv4(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "multi",
            arch_octet=["00:07", "00:09"],
            bootloader_path="bootx64.efi",
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert result[0]["test"] == (
            "option[93].hex == '0x07' or option[93].hex == '0x09'"
        )

    async def test_get_kea_bootloaders_arch_octet_uses_option_61_for_ipv6(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "uefi_amd64", arch_octet="00:07", bootloader_path="bootx64.efi"
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "fe80::1", ipv6=True
        )

        assert result[0] == {
            "name": "boot-uefi_amd64",
            "test": "option[61].hex == '0x07'",
            "option-data": [
                {
                    "name": "bootfile-url",
                    "data": "tftp://[fe80::1]/bootx64.efi",
                }
            ],
        }

    async def test_get_kea_bootloaders_user_class_ipxe_ipv4(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "ipxe",
            user_class="iPXE",
            bootloader_path="ipxe.cfg",
            path_prefix_http=True,
            absolute_url_as_filename=True,
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert result[0] == {
            "name": "boot-ipxe",
            "test": (
                "option[77].text == 'iPXE' or (option[175].option[19].exists "
                "and (option[175].option[24].exists or "
                "option[175].option[36].exists))"
            ),
            "boot-file-name": "http://10.0.0.1:5248/ipxe.cfg",
            "option-data": [],
        }

    async def test_get_kea_bootloaders_user_class_ipxe_ipv6(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "ipxe",
            user_class="iPXE",
            bootloader_path="ipxe.cfg",
            path_prefix_http=True,
            absolute_url_as_filename=True,
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "fe80::1", ipv6=True
        )

        assert result[0] == {
            "name": "boot-ipxe",
            "test": (
                "option[15].exists and option[15].text == 'iPXE' or "
                "(option[175].option[19].exists and "
                "(option[175].option[24].exists or "
                "option[175].option[36].exists))"
            ),
            "option-data": [
                {
                    "name": "bootfile-url",
                    "data": "http://[fe80::1]:5248/ipxe.cfg",
                }
            ],
        }

    async def test_get_kea_bootloaders_user_class_onie_uses_default_url(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "onie",
            user_class="onie_dhcp_user_class",
            bootloader_path="onie.cfg",
            path_prefix_http=True,
            absolute_url_as_filename=True,
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert result[0] == {
            "name": "boot-onie",
            "test": "option[77].text == 'onie_dhcp_user_class'",
            "default-url": "http://10.0.0.1:5248/onie.cfg",
            "option-data": [],
        }

    async def test_get_kea_bootloaders_skips_method_without_identifiers(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod("local", bootloader_path="local")

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert [cc["name"] for cc in result] == ["fallback-pxe"]

    async def test_get_kea_bootloaders_skips_onie_and_http_over_ipv6(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        onie = FakeBootMethod(
            "onie", user_class="onie_dhcp_user_class", bootloader_path="onie"
        )
        http = FakeBootMethod(
            "uefi_http",
            arch_octet="00:10",
            bootloader_path="bootx64.efi",
            http_url=True,
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [onie, http], "fe80::1", ipv6=True
        )

        assert [cc["name"] for cc in result] == ["fallback-uefi_amd64_tftp"]

    async def test_get_kea_bootloaders_path_prefix_force_adds_always_send(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "grub",
            arch_octet="00:0b",
            bootloader_path="grubaa64.efi",
            path_prefix="grub/",
            path_prefix_force=True,
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert result[0]["option-data"] == [
            {
                "name": "path-prefix",
                "data": "grub/",
                "always-send": True,
            }
        ]

    async def test_get_kea_bootloaders_http_url_adds_vendor_class(
        self, db: Database
    ) -> None:
        activities = self._make_activity(db)
        boot_method = FakeBootMethod(
            "uefi_http",
            arch_octet="00:10",
            bootloader_path="bootx64.efi",
            http_url=True,
            absolute_url_as_filename=True,
        )

        result = await activities.get_kea_bootloaders_client_classes(
            [boot_method], "10.0.0.1", ipv6=False
        )

        assert result[0] == {
            "name": "boot-uefi_http",
            "test": "option[93].hex == '0x10'",
            "boot-file-name": "http://10.0.0.1:5248/images/bootx64.efi",
            "option-data": [
                {
                    "name": "vendor-class-identifier",
                    "data": "HTTPClient",
                }
            ],
        }
