import random
from typing import Dict, List, Tuple

from netaddr import IPNetwork

from maasserver.models import Fabric, Subnet, VLAN
from maasserver.testing.commissioning import (
    FakeCommissioningData,
    LXDAddress,
    LXDNetwork,
)
from maastesting.factory import factory

from .defs import MACHINES_PER_FABRIC


def make_networks(
    count_per_fabric: int, fabrics_count
) -> Tuple[Dict[Fabric, List[VLAN]], Dict[VLAN, IPNetwork]]:
    fabrics = [Fabric.objects.create() for _ in range(fabrics_count)]
    vlans = {}
    ip_networks = {}
    created_cidrs = set()

    for fabric in fabrics:
        vlans[fabric] = [
            VLAN.objects.create(vid=vid, fabric=fabric)
            for vid in random.sample(range(10, 4095), count_per_fabric)
        ]
        for vlan in vlans[fabric]:
            cidr = factory.make_ipv4_network(slash=24, but_not=created_cidrs)
            created_cidrs.add(cidr)
            Subnet.objects.create(
                vlan=vlan,
                cidr=cidr,
            )
            ip_networks[vlan] = IPNetwork(cidr)

    return vlans, ip_networks


def make_network_interfaces(
    machine_infos: List[FakeCommissioningData],
    vlans: Dict[Fabric, List[VLAN]],
    ip_networks: Dict[VLAN, IPNetwork],
):
    machine_infos = list(machine_infos)

    def make_network_ip(vlan: VLAN, network: LXDNetwork):
        ip_network = ip_networks[vlan]
        ip = factory.pick_ip_in_network(ip_network)
        network.addresses = [LXDAddress(str(ip), ip_network.prefixlen)]
        return ip

    for fabric_vlans in vlans.values():
        if not machine_infos:
            return
        fabric_machine_infos, machine_infos = (
            machine_infos[:MACHINES_PER_FABRIC],
            machine_infos[MACHINES_PER_FABRIC:],
        )
        for machine_info in fabric_machine_infos:
            for idx, vlan in enumerate(fabric_vlans):
                network = machine_info.create_physical_network()
                if idx == 0:
                    bridge = machine_info.create_bridge_network(
                        mac_address=network.hwaddr, parents=[network]
                    )
                    make_network_ip(vlan, bridge)
                elif idx == 1:
                    vlan_iface = machine_info.create_vlan_network(
                        vid=vlan.vid, parent=network
                    )
                    make_network_ip(vlan, vlan_iface)
                elif idx == 2:
                    network2 = machine_info.create_physical_network()
                    bond = machine_info.create_bond_network(
                        parents=[network, network2]
                    )
                    make_network_ip(vlan, bond)
                else:
                    make_network_ip(vlan, network)
