from unittest.mock import Mock

import pytest

from maascommon.enums.dns import DnsUpdateAction
from maascommon.enums.interface import InterfaceType
from maascommon.enums.ipaddress import IpAddressType
from maascommon.enums.node import NodeStatus, NodeTypeEnum
from maascommon.enums.power import PowerState
from maasservicelayer.context import Context
from maasservicelayer.db.repositories.interfaces import InterfaceRepository
from maasservicelayer.models.domains import Domain
from maasservicelayer.models.fabrics import Fabric
from maasservicelayer.models.interfaces import Interface
from maasservicelayer.models.nodeconfigs import NodeConfig
from maasservicelayer.models.nodes import Node
from maasservicelayer.models.staticipaddress import StaticIPAddress
from maasservicelayer.models.subnets import Subnet
from maasservicelayer.models.vlans import Vlan
from maasservicelayer.services.dnspublications import DNSPublicationsService
from maasservicelayer.services.dnsresources import DNSResourcesService
from maasservicelayer.services.domains import DomainsService
from maasservicelayer.services.interfaces import InterfacesService
from maasservicelayer.services.nodes import NodesService
from maasservicelayer.services.temporal import TemporalService


@pytest.mark.asyncio
class TestInterfacesService:
    async def test_get_interfaces_in_fabric(self):
        temporal_service_mock = Mock(TemporalService)
        node_service_mock = Mock(NodesService)
        dnsresource_service_mock = Mock(DNSResourcesService)
        dnspublications_service_mock = Mock(DNSPublicationsService)
        domain_service_mock = Mock(DomainsService)

        interface_repository_mock = Mock(InterfaceRepository)

        interfaces_service = InterfacesService(
            context=Context(),
            temporal_service=temporal_service_mock,
            dnsresource_service=dnsresource_service_mock,
            dnspublication_service=dnspublications_service_mock,
            domain_service=domain_service_mock,
            node_service=node_service_mock,
            interface_repository=interface_repository_mock,
        )

        await interfaces_service.get_interfaces_in_fabric(fabric_id=0)

        interface_repository_mock.get_interfaces_in_fabric.assert_called_once_with(
            fabric_id=0
        )

    async def test_add_ip_creates_dnspublication(self):
        fabric = Fabric(id=7)
        vlan = Vlan(
            id=6,
            vid=0,
            description="",
            mtu=1500,
            dhcp_on=True,
            fabric_id=fabric.id,
        )
        subnet = Subnet(
            id=5,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            rdns_mode=1,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=vlan.id,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.1",
            alloc_type=IpAddressType.AUTO,
            lease_time=30,
            subnet_id=subnet.id,
        )
        node = Node(
            id=3,
            system_id="abcdef",
            hostname="test-node",
            status=NodeStatus.READY,
            power_state=PowerState.OFF,
            node_type=NodeTypeEnum.MACHINE,
        )
        node_config = NodeConfig(id=7, name="abc", node_id=node.id)
        node.current_config_id = node_config.id
        interface = Interface(
            id=1,
            name="testeth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            node_config_id=node_config.id,
        )
        domain = Domain(
            id=4,
            name="test-domain",
            authoritative=True,
            ttl=30,
        )

        temporal_service_mock = Mock(TemporalService)
        node_service_mock = Mock(NodesService)
        node_service_mock.get_one.return_value = node
        dnsresource_service_mock = Mock(DNSResourcesService)
        dnspublications_service_mock = Mock(DNSPublicationsService)
        domain_service_mock = Mock(DomainsService)
        domain_service_mock.get_domain_for_node.return_value = domain

        interface_repository_mock = Mock(InterfaceRepository)

        interface_service = InterfacesService(
            context=Context(),
            temporal_service=temporal_service_mock,
            dnsresource_service=dnsresource_service_mock,
            dnspublication_service=dnspublications_service_mock,
            domain_service=domain_service_mock,
            node_service=node_service_mock,
            interface_repository=interface_repository_mock,
        )
        await interface_service.add_ip(interface, sip)

        dnsresource_service_mock.add_ip.assert_called_once_with(
            sip, "testeth0.test-node", domain
        )
        dnspublications_service_mock.create_for_config_update.assert_called_once_with(
            source="ip 10.0.0.1 connected to test-node on testeth0",
            action=DnsUpdateAction.INSERT,
            label="testeth0.test-node",
            rtype="A",
            zone=domain.name,
        )

    async def test_remove_ip_creates_dnspublication(self):
        fabric = Fabric(id=7)
        vlan = Vlan(
            id=6,
            vid=0,
            description="",
            mtu=1500,
            dhcp_on=True,
            fabric_id=fabric.id,
        )
        subnet = Subnet(
            id=5,
            cidr="10.0.0.0/24",
            allow_dns=True,
            allow_proxy=True,
            active_discovery=True,
            rdns_mode=1,
            managed=True,
            disabled_boot_architectures=[],
            vlan_id=vlan.id,
        )
        sip = StaticIPAddress(
            id=2,
            ip="10.0.0.1",
            alloc_type=IpAddressType.AUTO,
            lease_time=30,
            subnet_id=subnet.id,
        )
        node = Node(
            id=3,
            system_id="abcdef",
            hostname="test-node",
            status=NodeStatus.READY,
            power_state=PowerState.OFF,
            node_type=NodeTypeEnum.MACHINE,
        )
        node_config = NodeConfig(id=7, name="abc", node_id=node.id)
        node.current_config_id = node_config.id
        interface = Interface(
            id=1,
            name="testeth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            node_config_id=node_config.id,
        )
        domain = Domain(
            id=4,
            name="test-domain",
            authoritative=True,
            ttl=30,
        )

        temporal_service_mock = Mock(TemporalService)
        node_service_mock = Mock(NodesService)
        node_service_mock.get_one.return_value = node
        dnsresource_service_mock = Mock(DNSResourcesService)
        dnspublications_service_mock = Mock(DNSPublicationsService)
        domain_service_mock = Mock(DomainsService)
        domain_service_mock.get_domain_for_node.return_value = domain

        interface_repository_mock = Mock(InterfaceRepository)

        interface_service = InterfacesService(
            context=Context(),
            temporal_service=temporal_service_mock,
            dnsresource_service=dnsresource_service_mock,
            dnspublication_service=dnspublications_service_mock,
            domain_service=domain_service_mock,
            node_service=node_service_mock,
            interface_repository=interface_repository_mock,
        )

        await interface_service.remove_ip(interface, sip)

        dnsresource_service_mock.remove_ip.assert_called_once_with(
            sip, "testeth0.test-node", domain
        )
        dnspublications_service_mock.create_for_config_update.assert_called_once_with(
            source="ip 10.0.0.1 disconnected from test-node on testeth0",
            action=DnsUpdateAction.DELETE,
            label="testeth0.test-node",
            rtype="A",
            zone=domain.name,
        )

    async def test__get_dns_label_for_interface_boot_interface(self):
        node = Node(
            id=3,
            system_id="abcdef",
            hostname="test-node",
            status=NodeStatus.READY,
            power_state=PowerState.OFF,
            node_type=NodeTypeEnum.MACHINE,
        )
        node_config = NodeConfig(id=7, name="abc", node_id=node.id)
        node.current_config_id = node_config.id
        interface = Interface(
            id=1,
            name="testeth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            node_config_id=node_config.id,
        )
        node.boot_interface_id = interface.id

        temporal_service_mock = Mock(TemporalService)
        node_service_mock = Mock(NodesService)
        dnsresource_service_mock = Mock(DNSResourcesService)
        dnspublications_service_mock = Mock(DNSPublicationsService)
        domain_service_mock = Mock(DomainsService)

        interface_repository_mock = Mock(InterfaceRepository)

        interface_service = InterfacesService(
            context=Context(),
            temporal_service=temporal_service_mock,
            dnsresource_service=dnsresource_service_mock,
            dnspublication_service=dnspublications_service_mock,
            domain_service=domain_service_mock,
            node_service=node_service_mock,
            interface_repository=interface_repository_mock,
        )

        dns_label = interface_service._get_dns_label_for_interface(
            interface, node
        )

        assert dns_label == node.hostname

    async def test__get_dns_label_for_interface_non_boot_interface(self):
        node = Node(
            id=3,
            system_id="abcdef",
            hostname="test-node",
            status=NodeStatus.READY,
            power_state=PowerState.OFF,
            node_type=NodeTypeEnum.MACHINE,
        )
        node_config = NodeConfig(id=7, name="abc", node_id=node.id)
        node.current_config_id = node_config.id
        interface = Interface(
            id=1,
            name="testeth0",
            mac_address="00:11:22:33:44:55",
            type=InterfaceType.PHYSICAL,
            node_config_id=node_config.id,
        )

        temporal_service_mock = Mock(TemporalService)
        node_service_mock = Mock(NodesService)
        dnsresource_service_mock = Mock(DNSResourcesService)
        dnspublications_service_mock = Mock(DNSPublicationsService)
        domain_service_mock = Mock(DomainsService)

        interface_repository_mock = Mock(InterfaceRepository)

        interface_service = InterfacesService(
            context=Context(),
            temporal_service=temporal_service_mock,
            dnsresource_service=dnsresource_service_mock,
            dnspublication_service=dnspublications_service_mock,
            domain_service=domain_service_mock,
            node_service=node_service_mock,
            interface_repository=interface_repository_mock,
        )

        dns_label = interface_service._get_dns_label_for_interface(
            interface, node
        )

        assert dns_label == f"{interface.name}.{node.hostname}"
