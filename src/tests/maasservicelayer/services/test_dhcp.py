# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from ipaddress import ip_address, ip_network
from unittest.mock import AsyncMock, Mock

from netaddr import IPAddress
import pytest

from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.ipranges import IPRangeType
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maascommon.enums.subnet import RdnsMode
from maasservicelayer.context import Context
from maasservicelayer.exceptions.catalog import (
    NotFoundException,
    ValidationException,
)
from maasservicelayer.filters.interfaces import InterfaceFilters
from maasservicelayer.filters.query import OrderBy
from maasservicelayer.filters.staticipaddress import StaticIPAddressFilters
from maasservicelayer.filters.subnets import SubnetFilters
from maasservicelayer.filters.vlans import VlansFilters
from maasservicelayer.models.dhcp import (
    DHCPDataForAgent,
    HostReservationData,
    InterfaceData,
    IPRangeData,
    KeaHAConfig,
    SubnetData,
    VlanData,
)
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.ipranges import IPRange
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.reservedips import ReservedIP
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services.configurations import ConfigurationsService
from maasservicelayer.services.dhcp import _DHCPQueryCache, DHCPService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.ipranges import IPRangesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.reservedips import ReservedIPsService
from maasservicelayer.services.staticipaddress import StaticIPAddressService
from maasservicelayer.services.subnets import SubnetsService
from maasservicelayer.services.vlans import VlansService
from maasservicelayer.utils.date import utcnow


@pytest.fixture
def rack():
    return Node(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        system_id="rack-1",
        hostname="rack",
        status=NodeStatus.DEPLOYED,
        node_type=NodeTypeEnum.RACK_CONTROLLER,
        power_state=PowerState.ON,
        current_config_id=1,
    )


@pytest.fixture
def vlan():
    return Vlan(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        vid=10,
        description="",
        mtu=1500,
        dhcp_on=True,
        primary_rack_id=1,
        fabric_id=1,
        space_id=1,
    )


@pytest.fixture
def subnet():
    return Subnet(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        cidr=ip_network("10.0.0.0/24"),
        rdns_mode=RdnsMode.DEFAULT,
        gateway_ip=ip_address("10.0.0.254"),
        allow_dns=True,
        allow_proxy=True,
        active_discovery=False,
        managed=True,
        disabled_boot_architectures=[],
        vlan_id=1,
    )


@pytest.fixture
def interface():
    return Interface(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        name="eth0",
        type=InterfaceType.PHYSICAL,
        mac_address="00:11:22:33:44:55",
        node_config_id=1,
        vlan_id=1,
    )


def make_ip(id=1, ip="10.0.0.1", subnet_id=1, alloc_type=IpAddressType.STICKY):
    return StaticIPAddress(
        id=id,
        created=utcnow(),
        updated=utcnow(),
        ip=ip_address(ip) if ip else None,
        alloc_type=alloc_type,
        lease_time=600,
        subnet_id=subnet_id,
    )


@pytest.fixture
def dhcp(rack, vlan, subnet, interface, monkeypatch):
    service = DHCPService(
        context=Context(),
        configurations_service=Mock(ConfigurationsService),
        domains_service=Mock(DomainsService),
        interfaces_service=Mock(InterfacesService),
        ipranges_service=Mock(IPRangesService),
        nodes_service=Mock(NodesService),
        reservedips_service=Mock(ReservedIPsService),
        staticipaddress_service=Mock(StaticIPAddressService),
        subnets_service=Mock(SubnetsService),
        vlans_service=Mock(VlansService),
    )
    service.nodes_service.get_one.return_value = rack
    service.nodes_service.get_by_id.return_value = rack
    service.nodes_service.get_url.return_value = ""
    service.nodes_service.get_many.return_value = []
    service.vlans_service.get_node_vlans.return_value = [vlan, vlan]
    service.vlans_service.get_many.return_value = [vlan]
    service.vlans_service.get_by_id.return_value = vlan
    service.subnets_service.get_many.return_value = [subnet]
    service.subnets_service.get_by_id.return_value = subnet
    service.interfaces_service.get_many.return_value = [interface]
    service.interfaces_service.get_for_ip.return_value = []
    service.interfaces_service.get_for_ips.return_value = {}
    service.staticipaddress_service.get_for_interfaces.return_value = [
        make_ip()
    ]
    service.staticipaddress_service.get_for_nodes.return_value = [make_ip()]
    service.staticipaddress_service.get_many.return_value = []
    service.ipranges_service.get_many.return_value = []
    service.reservedips_service.get_many.return_value = []
    service.domains_service.get_default_domain.return_value = Domain(
        id=1,
        created=utcnow(),
        updated=utcnow(),
        name="maas",
        authoritative=True,
    )
    service.domains_service.get_many.return_value = []
    service.configurations_service.get.side_effect = lambda name: {
        "maas_url": "http://region:5240/MAAS",
        "ntp_external_only": False,
        "ntp_servers": "ntp.example.com, ntp2.example.com",
        "use_rack_proxy": True,
    }[name]
    monkeypatch.setattr(
        "maasservicelayer.services.dhcp.get_source_address",
        lambda network: None,
    )
    monkeypatch.setattr(
        "maasservicelayer.services.dhcp.resolve_hostname",
        lambda hostname, version: {IPAddress("10.0.0.10")},
    )
    monkeypatch.setattr(
        "maasservicelayer.services.dhcp.MAAS_ID.get", lambda: None
    )
    return service


@pytest.mark.asyncio
class TestDHCPService:
    @pytest.mark.parametrize(
        "cidr,rack_ip,gateway,start,end",
        [
            (
                "10.0.0.0/24",
                "10.0.0.1",
                "10.0.0.254",
                "10.0.0.100",
                "10.0.0.200",
            ),
            (
                "2001:db8::/64",
                "2001:db8::1",
                "2001:db8::ffff",
                "2001:db8::100",
                "2001:db8::200",
            ),
        ],
    )
    async def test_get_kea_dhcp_data_for_agent(
        self,
        dhcp,
        subnet,
        interface,
        cidr,
        rack_ip,
        gateway,
        start,
        end,
        monkeypatch,
    ):
        subnet.cidr = ip_network(cidr)
        subnet.gateway_ip = ip_address(gateway)
        rack_address = make_ip(ip=rack_ip)
        dhcp.staticipaddress_service.get_for_interfaces.return_value = [
            rack_address
        ]
        dhcp.staticipaddress_service.get_for_nodes.return_value = [
            rack_address
        ]
        iprange = IPRange(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            type=IPRangeType.DYNAMIC,
            start_ip=ip_address(start),
            end_ip=ip_address(end),
            subnet_id=1,
        )
        dhcp.ipranges_service.get_many.return_value = [iprange]
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname",
            lambda hostname, version: set(),
        )
        pool = IPRangeData(1, 1, True, start, end)

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert result == DHCPDataForAgent(
            vlans=[VlanData(1, 10, None, 1500)],
            subnets=[
                SubnetData(
                    id=1,
                    rack_system_id="rack-1",
                    secondary_rack_system_id=None,
                    ip_version=subnet.cidr.version,
                    cidr=cidr,
                    gateway_ip=gateway,
                    dns_servers=[rack_ip],
                    allow_dns=True,
                    vlan_id=1,
                    vlan_mtu=1500,
                    mask=str(subnet.cidr.netmask),
                    broadcast_ip=str(subnet.cidr.broadcast_address),
                    domain_name="maas",
                    search_list=["maas"],
                    ntp_servers=[rack_ip],
                    next_server=rack_ip,
                    pools=[pool],
                    host_reservations=[],
                )
            ],
            ipranges=[pool],
            interfaces=[InterfaceData(1, 1, interface.name)],
            default_dns_servers=[rack_ip],
            ntp_servers=[rack_ip],
            ha_data=[],
        )

    async def test_only_includes_owned_dhcp_vlans_and_managed_subnets(
        self, dhcp, rack
    ):
        await dhcp.get_kea_dhcp_data_for_agent(rack.system_id)

        vlan_query = dhcp.vlans_service.get_many.call_args_list[0].args[0]
        assert vlan_query.where == VlansFilters.and_filters(
            [
                VlansFilters.with_dhcp_on(True),
                VlansFilters.with_primary_or_secondary_rack_id(rack.id),
            ]
        )
        assert vlan_query.order_by == (OrderBy(Vlan, "id"),)
        subnet_query = dhcp.subnets_service.get_many.call_args_list[0].kwargs[
            "query"
        ]
        assert subnet_query.where == SubnetFilters.and_filters(
            [
                SubnetFilters.with_vlan_id_in([1]),
                SubnetFilters.with_managed(True),
            ]
        )

    async def test_subnets_and_pools_are_sorted_and_only_dynamic_ranges_are_pools(
        self, dhcp, subnet, vlan
    ):
        later_subnet = subnet.model_copy(
            update={
                "id": 2,
                "cidr": ip_network("10.0.1.0/24"),
            }
        )
        dhcp.subnets_service.get_many.return_value = [later_subnet, subnet]
        dynamic_range = IPRange(
            id=2,
            created=utcnow(),
            updated=utcnow(),
            type=IPRangeType.DYNAMIC,
            start_ip=ip_address("10.0.1.100"),
            end_ip=ip_address("10.0.1.200"),
            subnet_id=2,
        )
        reserved_range = IPRange(
            id=1,
            created=utcnow(),
            updated=utcnow(),
            type=IPRangeType.RESERVED,
            start_ip=ip_address("10.0.0.100"),
            end_ip=ip_address("10.0.0.200"),
            subnet_id=1,
        )
        dhcp.ipranges_service.get_many.return_value = [
            reserved_range,
            dynamic_range,
        ]

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert [subnet.cidr for subnet in result.subnets] == [
            "10.0.0.0/24",
            "10.0.1.0/24",
        ]
        assert [
            pool.id for subnet in result.subnets for pool in subnet.pools
        ] == [2]
        assert [pool.id for pool in result.ipranges] == [1, 2]

    async def test_unconfigured_address_family_is_omitted(
        self, dhcp, subnet, interface
    ):
        subnet.cidr = ip_network("2001:db8::/64")

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert result.subnets == []
        assert result.ipranges == []
        assert result.interfaces == []

    async def test_unattached_owned_vlan_is_omitted(self, dhcp, interface):
        dhcp.interfaces_service.get_many.return_value = [
            interface.model_copy(update={"vlan_id": 2})
        ]
        dhcp.subnets_service.get_many.return_value = []

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert result.vlans == []
        assert result.subnets == []

    async def test_subnets_without_an_interface_in_same_family_remain_configured(
        self, dhcp, subnet, interface
    ):
        subnet.cidr = ip_network("2001:db8::/64")
        dhcp.staticipaddress_service.get_for_interfaces.return_value = [
            make_ip(ip="2001:db8::1")
        ]
        dhcp.staticipaddress_service.get_for_nodes.return_value = [
            make_ip(ip="2001:db8::1")
        ]

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert result.subnets[0].ip_version == 6

    @pytest.mark.parametrize(
        "node_type,current_config_id,error",
        [
            (NodeTypeEnum.MACHINE, 1, ValidationException),
            (NodeTypeEnum.REGION_CONTROLLER, 1, ValidationException),
            (NodeTypeEnum.RACK_CONTROLLER, None, ValidationException),
        ],
    )
    async def test_rejects_invalid_rack(
        self, dhcp, rack, node_type, current_config_id, error
    ):
        rack.node_type = node_type
        rack.current_config_id = current_config_id
        with pytest.raises(error):
            await dhcp.get_kea_dhcp_data_for_agent(rack.system_id)

    async def test_missing_rack(self, dhcp):
        dhcp.nodes_service.get_one.return_value = None
        with pytest.raises(NotFoundException):
            await dhcp.get_kea_dhcp_data_for_agent("missing")

    async def test_external_ntp_and_rack_url(self, dhcp, monkeypatch):
        dhcp.nodes_service.get_url.return_value = (
            "http://rack-region:5240/MAAS"
        )
        dhcp.configurations_service.get.side_effect = lambda name: {
            "ntp_external_only": True,
            "ntp_servers": "ntp.example.com, ntp2.example.com",
            "use_rack_proxy": True,
        }[name]
        resolver = Mock(return_value=set())
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname", resolver
        )
        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")
        assert result.ntp_servers == ["ntp.example.com", "ntp2.example.com"]
        assert result.subnets[0].ntp_servers == result.ntp_servers
        resolver.assert_called_once_with("rack-region", 4)

    async def test_relay_uses_serving_vlan_interface(self, dhcp, subnet, vlan):
        relay = vlan.model_copy(
            update={
                "id": 2,
                "vid": 20,
                "relay_vlan_id": 1,
                "dhcp_on": False,
            }
        )
        serving_subnet = subnet.model_copy()
        subnet.id = 2
        subnet.vlan_id = 2
        subnet.cidr = ip_network("10.1.0.0/24")
        dhcp.vlans_service.get_many.side_effect = [
            [vlan],
            [relay],
            [relay],
        ]
        dhcp.subnets_service.get_by_id.return_value = serving_subnet
        dhcp._get_default_dns_servers_for_subnet = AsyncMock(return_value=[])

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert [v.id for v in result.vlans] == [1, 2]
        assert result.subnets[0].vlan_id == 2
        assert result.subnets[0].next_server == "10.0.0.1"
        assert result.interfaces == [InterfaceData(1, 1, "eth0")]

    async def test_relay_subnet_uses_serving_vlan_ha_pair(
        self, dhcp, subnet, vlan
    ):
        serving = vlan.model_copy(update={"secondary_rack_id": 2})
        relay = vlan.model_copy(
            update={
                "id": 2,
                "vid": 20,
                "relay_vlan_id": 1,
                "dhcp_on": False,
                "primary_rack_id": None,
                "secondary_rack_id": None,
            }
        )
        relay_subnet = subnet.model_copy(update={"id": 2, "vlan_id": 2})
        dhcp.vlans_service.get_many.side_effect = [[serving], [relay]]
        dhcp.subnets_service.get_many.return_value = [relay_subnet]
        ha = KeaHAConfig("rack-1", "rack-2", "10.0.0.1", "10.0.0.2")
        dhcp._get_ha_config = AsyncMock(return_value=ha)
        dhcp._get_ntp_servers_for_rack = AsyncMock(return_value={})
        dhcp._get_default_dns_servers_for_subnet = AsyncMock(return_value=[])

        result = await dhcp.get_kea_dhcp_data_for_agent("rack-1")

        assert result.ha_data == [ha]
        assert result.subnets[0].secondary_rack_system_id == "rack-2"
        ha_vlan = dhcp._get_ha_config.call_args.args[1]
        assert ha_vlan.id == 1

    async def test_base_vlan_does_not_select_interface_from_relay_vlan(
        self, dhcp, subnet, vlan, interface
    ):
        relay_subnet = subnet.model_copy(update={"id": 2, "vlan_id": 2})
        dhcp.staticipaddress_service.get_for_interfaces.return_value = [
            make_ip(subnet_id=2)
        ]
        dhcp.subnets_service.get_by_id.return_value = relay_subnet

        selected, addresses = await dhcp._get_best_interface_with_ip_on_vlan(
            subnet, vlan, [interface], _DHCPQueryCache()
        )

        assert selected is None
        assert addresses == []

    @pytest.mark.parametrize("system_id", ["rack-1", "rack-2"])
    async def test_ha_roles_are_independent_of_requesting_rack(
        self, dhcp, rack, vlan, interface, subnet, system_id
    ):
        secondary = rack.model_copy(
            update={
                "id": 2,
                "system_id": "rack-2",
                "current_config_id": 2,
            }
        )
        secondary_interface = interface.model_copy(
            update={
                "id": 2,
                "node_config_id": 2,
            }
        )
        vlan.secondary_rack_id = secondary.id
        dhcp.nodes_service.get_one.return_value = (
            rack if system_id == rack.system_id else secondary
        )
        dhcp.nodes_service.get_by_id.side_effect = lambda id: {
            1: rack,
            2: secondary,
        }[id]
        dhcp.interfaces_service.get_many.side_effect = lambda query: (
            [interface]
            if query.where == InterfaceFilters.with_node_config_id(1)
            else [secondary_interface]
        )
        dhcp.staticipaddress_service.get_for_interfaces.side_effect = (
            lambda ids: [make_ip(ip=f"10.0.0.{ids[0]}")]
        )
        dhcp.subnets_service.get_many.return_value = [subnet, subnet]
        dhcp._get_ntp_servers_for_rack = AsyncMock(
            side_effect=[
                {(1, 4): "10.0.0.1"},
                {(1, 4): "10.0.0.2"},
            ]
        )
        result = await dhcp.get_kea_dhcp_data_for_agent(system_id)
        assert result.ha_data == [
            KeaHAConfig("rack-1", "rack-2", "10.0.0.1", "10.0.0.2")
        ]
        assert result.interfaces == [
            InterfaceData(1 if system_id == "rack-1" else 2, 1, "eth0")
        ]
        assert result.subnets[0].ntp_servers == ["10.0.0.1", "10.0.0.2"]

    async def test_ha_without_address_fails(self, dhcp, subnet, vlan):
        vlan.secondary_rack_id = 2
        dhcp.staticipaddress_service.get_for_interfaces.return_value = []
        with pytest.raises(ValidationException):
            await dhcp._get_ha_config(subnet, vlan, _DHCPQueryCache())

    @pytest.mark.parametrize(
        "first_type,first_alloc,second_type,second_alloc,expected",
        [
            (
                InterfaceType.BOND,
                IpAddressType.DISCOVERED,
                InterfaceType.PHYSICAL,
                IpAddressType.STICKY,
                2,
            ),
            (
                InterfaceType.PHYSICAL,
                IpAddressType.STICKY,
                InterfaceType.BOND,
                IpAddressType.STICKY,
                2,
            ),
            (
                InterfaceType.VLAN,
                IpAddressType.AUTO,
                InterfaceType.PHYSICAL,
                IpAddressType.AUTO,
                2,
            ),
        ],
    )
    async def test_interface_preference(
        self,
        dhcp,
        subnet,
        vlan,
        interface,
        first_type,
        first_alloc,
        second_type,
        second_alloc,
        expected,
    ):
        first = interface.model_copy(update={"type": first_type})
        second = interface.model_copy(update={"id": 2, "type": second_type})
        dhcp.staticipaddress_service.get_for_interfaces.side_effect = (
            lambda ids: [
                make_ip(alloc_type=first_alloc if ids == [1] else second_alloc)
            ]
        )
        best, _ = await dhcp._get_best_interface_with_ip_on_vlan(
            subnet, vlan, [first, second], _DHCPQueryCache()
        )
        assert best.id == expected

    async def test_legacy_selection_does_not_filter_disabled_interfaces(
        self, dhcp, subnet, vlan, interface
    ):
        disabled = interface.model_copy(update={"enabled": False})
        dhcp.staticipaddress_service.get_for_interfaces.side_effect = (
            lambda ids: [
                make_ip() if ids == [1] else make_ip(ip="2001:db8::1")
            ]
        )
        selected, addresses = await dhcp._get_best_interface_with_ip_on_vlan(
            subnet,
            vlan,
            [disabled, interface.model_copy(update={"id": 2})],
            _DHCPQueryCache(),
        )
        assert selected.id == 1
        assert [address.ip for address in addresses] == [
            ip_address("10.0.0.1")
        ]

    async def test_interface_ties_follow_creation_time(
        self, dhcp, subnet, vlan, interface
    ):
        earlier = interface.model_copy(update={"type": InterfaceType.PHYSICAL})
        later = interface.model_copy(
            update={
                "id": 2,
                "type": InterfaceType.PHYSICAL,
                "created": interface.created.replace(
                    year=interface.created.year + 1
                ),
            }
        )
        dhcp.staticipaddress_service.get_for_interfaces.return_value = [
            make_ip()
        ]
        selected, _ = await dhcp._get_best_interface_with_ip_on_vlan(
            subnet, vlan, [later, earlier], _DHCPQueryCache()
        )
        assert selected.id == 1

    async def test_dynamic_pools_break_interface_ties(
        self, dhcp, subnet, vlan, interface
    ):
        other_subnet = subnet.model_copy(update={"id": 2})
        second = interface.model_copy(update={"id": 2})
        dhcp.staticipaddress_service.get_for_interfaces.side_effect = (
            lambda ids: [make_ip(subnet_id=ids[0])]
        )
        dhcp.subnets_service.get_by_id.side_effect = lambda id: {
            1: subnet,
            2: other_subnet,
        }[id]
        dhcp.ipranges_service.get_many.side_effect = [[], [Mock(IPRange)]]

        best, _ = await dhcp._get_best_interface_with_ip_on_vlan(
            subnet, vlan, [interface, second], _DHCPQueryCache()
        )

        assert best.id == 2

    async def test_bond_hosts_precede_bond_and_duplicate_reserved_macs_remain(
        self, dhcp, interface
    ):
        bond = interface.model_copy(update={"type": InterfaceType.BOND})
        parent = interface.model_copy(
            update={
                "id": 2,
                "name": "eth0.10",
                "mac_address": "00:11:22:33:44:66",
            }
        )
        same_mac_parent = interface.model_copy(update={"id": 3})
        dhcp.staticipaddress_service.get_many.return_value = [make_ip()]
        dhcp.interfaces_service.get_for_ips.return_value = {1: [bond, parent]}
        dhcp.interfaces_service.get_parents.return_value = [
            same_mac_parent,
            parent,
        ]
        dhcp.reservedips_service.get_many.return_value = [
            ReservedIP(
                id=id,
                created=utcnow(),
                updated=utcnow(),
                ip=ip_address("10.0.0.100"),
                mac_address=mac,
                subnet_id=1,
            )
            for id, mac in [
                (1, bond.mac_address),
                (2, "00:11:22:33:44:77"),
                (3, "00:11:22:33:44:77"),
            ]
        ]
        hosts = await dhcp._get_dhcp_host_reservations([1])
        assert hosts[1] == [
            HostReservationData(
                "10.0.0.1", parent.mac_address, "rack-eth0-10"
            ),
            HostReservationData("10.0.0.1", bond.mac_address, "rack-eth0"),
            HostReservationData("10.0.0.100", "00:11:22:33:44:77", "rsvd-2"),
            HostReservationData("10.0.0.100", "00:11:22:33:44:77", "rsvd-3"),
        ]
        query = dhcp.staticipaddress_service.get_many.call_args.kwargs["query"]
        expected = StaticIPAddressFilters.and_filters(
            [
                StaticIPAddressFilters.with_subnet_id_in([1]),
                StaticIPAddressFilters.with_alloc_type_in(
                    [
                        IpAddressType.AUTO,
                        IpAddressType.STICKY,
                        IpAddressType.USER_RESERVED,
                    ]
                ),
                StaticIPAddressFilters.with_ip_not_null(),
                StaticIPAddressFilters.with_temp_expires_on_is_null(),
            ]
        )
        assert query.where == expected
        assert query.order_by == (OrderBy(StaticIPAddress, "id"),)

    async def test_host_interface_deduplication_spans_vlan_subnets(
        self, dhcp, interface
    ):
        dhcp.staticipaddress_service.get_many.return_value = [
            make_ip(id=1, subnet_id=1),
            make_ip(id=2, ip="10.0.1.1", subnet_id=2),
        ]
        dhcp.interfaces_service.get_for_ips.return_value = {
            1: [interface],
            2: [interface],
        }

        hosts = await dhcp._get_dhcp_host_reservations([1, 2])

        assert hosts[1] == [
            HostReservationData("10.0.0.1", interface.mac_address, "rack-eth0")
        ]
        assert hosts[2] == []

    async def test_ntp_prefers_dhcp_vlan_without_relying_on_group_order(
        self, dhcp, rack, subnet, vlan
    ):
        other_vlan = vlan.model_copy(update={"id": 2, "dhcp_on": False})
        other_subnet = subnet.model_copy(update={"id": 2, "vlan_id": 2})
        dhcp.staticipaddress_service.get_for_nodes.return_value = [
            make_ip(ip="10.0.0.1", subnet_id=2),
            make_ip(ip="2001:db8::1", subnet_id=1),
            make_ip(ip="10.0.0.20", subnet_id=1),
            make_ip(ip="10.0.0.10", subnet_id=1),
        ]
        dhcp.subnets_service.get_by_id.side_effect = lambda id: {
            1: subnet,
            2: other_subnet,
        }[id]
        dhcp.vlans_service.get_by_id.side_effect = lambda id: {
            1: vlan,
            2: other_vlan,
        }[id]
        assert await dhcp._get_ntp_servers_for_rack(
            rack, _DHCPQueryCache()
        ) == {
            (1, 4): "10.0.0.10",
            (1, 6): "2001:db8::1",
        }

    async def test_dns_preserves_explicit_servers_when_maas_dns_disabled(
        self, dhcp, subnet
    ):
        subnet.allow_dns = False
        subnet.dns_servers = ["9.9.9.9"]
        assert await dhcp._get_default_dns_servers_for_subnet(
            subnet, "region", _DHCPQueryCache()
        ) == ["9.9.9.9"]

    async def test_dns_resolution_failure_still_uses_rack(
        self, dhcp, subnet, monkeypatch
    ):
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname",
            Mock(side_effect=OSError("unresolvable")),
        )
        assert await dhcp._get_default_dns_servers_for_subnet(
            subnet, "region", _DHCPQueryCache()
        ) == ["10.0.0.1"]

    async def test_dns_servers_are_sorted_and_filtered_by_allow_dns(
        self, dhcp, subnet, monkeypatch
    ):
        disallowed = subnet.model_copy(update={"allow_dns": False})
        dhcp.subnets_service.find_best_subnet_for_ip.side_effect = lambda ip: (
            disallowed if ip == ip_address("10.0.0.20") else None
        )
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname",
            lambda hostname, version: {
                IPAddress("10.0.0.20"),
                IPAddress("10.0.0.10"),
            },
        )

        servers = await dhcp._get_default_dns_servers_for_subnet(
            subnet, "http://region:5240/MAAS", _DHCPQueryCache()
        )

        assert servers == ["10.0.0.1", "10.0.0.10"]

    async def test_dns_prefers_non_loopback_addresses(
        self, dhcp, subnet, monkeypatch
    ):
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname",
            lambda hostname, version: {
                IPAddress("127.0.0.1"),
                IPAddress("10.0.0.10"),
            },
        )

        servers = await dhcp._get_default_dns_servers_for_subnet(
            subnet, "region", _DHCPQueryCache()
        )

        assert "127.0.0.1" not in servers

    async def test_alternate_region_dns_is_limited_to_source_subnet(
        self, dhcp, rack, subnet
    ):
        dhcp.nodes_service.get_many.return_value = [rack]
        dhcp.staticipaddress_service.get_for_nodes.return_value = [
            make_ip(ip="10.0.0.20")
        ]
        dhcp.subnets_service.find_best_subnet_for_ip.return_value = subnet

        addresses = await dhcp._get_alt_region_ips_for_dns(
            [ip_address("10.0.0.10")]
        )

        assert addresses == [ip_address("10.0.0.20")]
        query = dhcp.staticipaddress_service.get_for_nodes.call_args.kwargs[
            "query"
        ]
        assert query.where == StaticIPAddressFilters.and_filters(
            [
                StaticIPAddressFilters.with_node_system_id("rack-1"),
                StaticIPAddressFilters.with_subnet_id(subnet.id),
                StaticIPAddressFilters.with_ip_not_null(),
            ]
        )
        assert query.order_by == (OrderBy(StaticIPAddress, "ip"),)

    async def test_dns_prioritizes_rack_and_deduplicates_explicit_servers(
        self, dhcp, subnet
    ):
        subnet.dns_servers = ["10.0.0.10", "9.9.9.9"]
        assert await dhcp._get_default_dns_servers_for_subnet(
            subnet, "region", _DHCPQueryCache()
        ) == ["10.0.0.1", "10.0.0.10", "9.9.9.9"]

    async def test_dns_falls_back_to_region_when_hostname_is_unresolvable(
        self, dhcp, subnet, monkeypatch
    ):
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.get_source_address",
            lambda network: "10.0.0.10",
        )
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname",
            Mock(side_effect=OSError("unresolvable")),
        )
        dhcp._get_boot_rack_controller_ips = AsyncMock(return_value=[])

        assert await dhcp._get_default_dns_servers_for_subnet(
            subnet, "region", _DHCPQueryCache()
        ) == ["10.0.0.10"]

    async def test_dns_without_gateway_filters_automatic_servers(
        self, dhcp, subnet, monkeypatch
    ):
        subnet.gateway_ip = None
        subnet.dns_servers = ["9.9.9.9"]
        monkeypatch.setattr(
            "maasservicelayer.services.dhcp.resolve_hostname",
            lambda hostname, version: {IPAddress("192.0.2.1")},
        )
        assert await dhcp._get_default_dns_servers_for_subnet(
            subnet, "region", _DHCPQueryCache()
        ) == ["10.0.0.1", "9.9.9.9"]

    async def test_alternate_region_dns_requires_a_resolved_server(self, dhcp):
        assert await dhcp._get_alt_region_ips_for_dns([]) == []
        dhcp.staticipaddress_service.get_for_nodes.assert_not_called()
