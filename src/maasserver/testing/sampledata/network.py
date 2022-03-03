import random
from typing import Dict, List

from netaddr import IPNetwork

from maasserver.models import Fabric, Subnet, VLAN
from maasserver.testing.commissioning import FakeCommissioningData, LXDAddress
from maastesting.factory import factory

from .defs import MACHINES_PER_FABRIC


def make_networks(count_per_fabric: int, fabrics_count):
    fabrics = [Fabric.objects.create() for _ in range(fabrics_count)]
    vlans = {}
    ip_networks = {}
    created_cidrs = set()

    for fabric in fabrics:
        vlans[fabric] = [
            VLAN.objects.create(vid=vid, fabric=fabric)
            for vid in random.sample(range(10, 4096), count_per_fabric)
        ]
        for vlan in vlans[fabric]:
            cidr = factory.make_ipv4_network(slash=24, but_not=created_cidrs)
            Subnet.objects.create(
                vlan=vlan,
                cidr=cidr,
            )
            ip_networks[vlan] = IPNetwork(cidr)

    return vlans, ip_networks


def make_network_interfaces(
    machine_infos: List[FakeCommissioningData],
    vlans: Dict[Fabric, VLAN],
    ip_networks: Dict[VLAN, IPNetwork],
):
    machine_infos = list(machine_infos)
    for vlans in vlans.values():
        fabric_machine_infos = [
            machine_infos.pop()
            for _ in range(MACHINES_PER_FABRIC)
            if machine_infos
        ]
        for machine_info in fabric_machine_infos:
            for vlan in vlans:
                network = machine_info.create_physical_network()
                ip_network = ip_networks[vlan]
                ip = factory.pick_ip_in_network(ip_network)
                network.addresses = [LXDAddress(ip, ip_network.prefixlen)]
