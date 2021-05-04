# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Construct sample application data dynamically."""


from collections import defaultdict
from datetime import timedelta
import random
from socket import gethostname
from textwrap import dedent

from maasserver.enum import (
    ALLOCATED_NODE_STATUSES,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.models import (
    Domain,
    Fabric,
    Node,
    RackController,
    User,
    VersionedTextFile,
)
from maasserver.models.virtualmachine import get_vm_host_used_resources
from maasserver.storage_layouts import STORAGE_LAYOUTS
from maasserver.testing.factory import factory
from maasserver.tests.test_storage_layouts import LARGE_BLOCK_DEVICE
from maasserver.utils.orm import get_one, transactional
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import (
    SCRIPT_STATUS,
    SCRIPT_STATUS_FAILED,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
    SCRIPT_TYPE,
)
from metadataserver.fields import Bin
from metadataserver.models import Script, ScriptSet
from provisioningserver.drivers.pod import Capabilities
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.ipaddr import get_mac_addresses


class RandomInterfaceFactory:
    @classmethod
    def create_random(cls, node):
        """Create a random interface configuration for `node`."""
        creator = random.choice(
            [
                cls._create_basic,
                cls._create_bond,
                cls._create_vlan,
                cls._create_bond_vlan,
            ]
        )
        creator(node)

    @classmethod
    def _create_basic(cls, node, fabric=None, assign_ips=True):
        """Create 3 physical interfaces on `node`."""
        interfaces = []
        for _ in range(3):
            if fabric is None:
                fabric = random.choice(list(Fabric.objects.all()))
            vlan = fabric.get_default_vlan()
            interface = factory.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan
            )
            interfaces.append(interface)
            if assign_ips:
                cls.assign_ip(interface)
        return interfaces

    @classmethod
    def _create_bond(cls, node):
        """Create a bond interface from the 3 created physical interfaces."""
        fabric = random.choice(list(Fabric.objects.all()))
        vlan = fabric.get_default_vlan()
        parents = cls._create_basic(node, fabric=fabric, assign_ips=False)
        bond = factory.make_Interface(
            INTERFACE_TYPE.BOND, node=node, vlan=vlan, parents=parents
        )
        cls.assign_ip(bond)
        return bond

    @classmethod
    def _create_vlan(cls, node, parents=None):
        """Create a VLAN interface one for each of the 3 created physical
        interfaces."""
        interfaces = []
        if parents is None:
            parents = cls._create_basic(node)
        for parent in parents:
            tagged_vlans = list(
                parent.vlan.fabric.vlan_set.exclude(id=parent.vlan.id)
            )
            if len(tagged_vlans) > 0:
                vlan = random.choice(tagged_vlans)
            else:
                vlan = factory.make_VLAN(fabric=parent.vlan.fabric)
            vlan_interface = factory.make_Interface(
                INTERFACE_TYPE.VLAN, node=node, vlan=vlan, parents=[parent]
            )
            interfaces.append(vlan_interface)
            cls.assign_ip(vlan_interface)
        return interfaces

    @classmethod
    def _create_bond_vlan(cls, node):
        """Create a bond interface with a VLAN interface on that bond."""
        bond = cls._create_bond(node)
        cls._create_vlan(node, parents=[bond])

    @classmethod
    def assign_ip(cls, interface, alloc_type=None):
        """Assign an IP address to the interface."""
        subnets = list(interface.vlan.subnet_set.all())
        if len(subnets) > 0:
            subnet = random.choice(subnets)
            if alloc_type is None:
                alloc_type = random.choice(
                    [IPADDRESS_TYPE.STICKY, IPADDRESS_TYPE.AUTO]
                )
            if (
                alloc_type == IPADDRESS_TYPE.AUTO
                and interface.node.status
                not in [
                    NODE_STATUS.DEPLOYING,
                    NODE_STATUS.DEPLOYED,
                    NODE_STATUS.FAILED_DEPLOYMENT,
                    NODE_STATUS.RELEASING,
                ]
            ):
                assign_ip = ""
            else:
                # IPv6 use pick_ip_in_network as pick_ip_in_Subnet takes
                # forever with the IPv6 network.
                network = subnet.get_ipnetwork()
                if network.version == 6:
                    assign_ip = factory.pick_ip_in_network(network)
                else:
                    assign_ip = factory.pick_ip_in_Subnet(subnet)
            factory.make_StaticIPAddress(
                alloc_type=alloc_type,
                subnet=subnet,
                ip=assign_ip,
                interface=interface,
            )


def populate(seed="sampledata"):
    """Populate the database with example data.

    This should:

    - Mimic a real-world MAAS installation,

    - Create example data for all of MAAS's features,

    - Not go overboard; in general there need be at most a handful of each
      type of object,

    - Have elements of randomness; the sample data should never become
      something we depend upon too closely — for example in QA, demos, and
      tests — and randomness helps to keep us honest.

    If there is something you need, add it. If something does not make sense,
    change it or remove it. If you need something esoteric that would muddy
    the waters for the majority, consider putting it in a separate function.

    This function expects to be run into an empty database. It is not
    idempotent, and will almost certainly crash if invoked multiple times on
    the same database.

    """
    random.seed(seed)
    populate_main()
    # fetch and pass in all racks w/networking details so it's only done once
    racks = _prefetch_racks()
    for _ in range(120):
        make_discovery(racks=racks)


@transactional
def make_discovery(racks=None):
    """Make a discovery in its own transaction so each last_seen time is
    different.

    """
    if racks is None:
        racks = _prefetch_racks()
    rack = random.choice(racks)
    interface = random.choice(rack.interface_set.all())
    subnet = random.choice(interface.vlan.subnet_set.all())
    factory.make_Discovery(
        interface=interface, ip=factory.pick_ip_in_Subnet(subnet)
    )


def _prefetch_racks():
    """Prefetch all RackControllers and their networking details.

    This avoids extra queries to pick interfaces and subnets from each rack.

    """
    return list(
        RackController.objects.all().prefetch_related(
            "interface_set", "interface_set__vlan__subnet_set"
        )
    )


@transactional
def populate_main():
    """Populate the main data all in one transaction."""
    admin = factory.make_admin(
        username="admin", password="test", completed_intro=False
    )  # noqa
    user1, _ = factory.make_user_with_keys(
        username="user1", password="test", completed_intro=False
    )
    user2, _ = factory.make_user_with_keys(
        username="user2", password="test", completed_intro=False
    )

    # Physical zones.
    zones = [
        factory.make_Zone(name="zone-north"),
        factory.make_Zone(name="zone-south"),
    ]

    # DNS domains.
    domains = [
        Domain.objects.get_default_domain(),
        factory.make_Domain("sample"),
        factory.make_Domain("ubnt"),
    ]

    # Create the fabrics that will be used by the regions, racks,
    # machines, and devices.
    fabric0 = Fabric.objects.get_default_fabric()
    fabric0_untagged = fabric0.get_default_vlan()
    fabric0_vlan10 = factory.make_VLAN(fabric=fabric0, vid=10)
    fabric1 = factory.make_Fabric()
    fabric1_untagged = fabric1.get_default_vlan()
    fabric1_vlan42 = factory.make_VLAN(fabric=fabric1, vid=42)
    empty_fabric = factory.make_Fabric()  # noqa

    # Create some spaces.
    space_mgmt = factory.make_Space("management")
    space_storage = factory.make_Space("storage")
    space_internal = factory.make_Space("internal")
    space_ipv6_testbed = factory.make_Space("ipv6-testbed")

    # Subnets used by regions, racks, machines, and devices.
    subnet_1 = factory.make_Subnet(
        cidr="172.16.1.0/24",
        gateway_ip="172.16.1.1",
        vlan=fabric0_untagged,
        space=space_mgmt,
    )
    subnet_2 = factory.make_Subnet(
        cidr="172.16.2.0/24",
        gateway_ip="172.16.2.1",
        vlan=fabric1_untagged,
        space=space_mgmt,
    )
    subnet_3 = factory.make_Subnet(
        cidr="172.16.3.0/24",
        gateway_ip="172.16.3.1",
        vlan=fabric0_vlan10,
        space=space_storage,
    )
    subnet_4 = factory.make_Subnet(  # noqa
        cidr="172.16.4.0/24",
        gateway_ip="172.16.4.1",
        vlan=fabric0_vlan10,
        space=space_internal,
    )
    subnet_2001_db8_42 = factory.make_Subnet(  # noqa
        cidr="2001:db8:42::/64",
        gateway_ip="",
        vlan=fabric1_vlan42,
        space=space_ipv6_testbed,
    )
    ipv4_subnets = [subnet_1, subnet_2, subnet_3, subnet_4]

    # Static routes on subnets.
    factory.make_StaticRoute(source=subnet_1, destination=subnet_2)
    factory.make_StaticRoute(source=subnet_1, destination=subnet_3)
    factory.make_StaticRoute(source=subnet_1, destination=subnet_4)
    factory.make_StaticRoute(source=subnet_2, destination=subnet_1)
    factory.make_StaticRoute(source=subnet_2, destination=subnet_3)
    factory.make_StaticRoute(source=subnet_2, destination=subnet_4)
    factory.make_StaticRoute(source=subnet_3, destination=subnet_1)
    factory.make_StaticRoute(source=subnet_3, destination=subnet_2)
    factory.make_StaticRoute(source=subnet_3, destination=subnet_4)
    factory.make_StaticRoute(source=subnet_4, destination=subnet_1)
    factory.make_StaticRoute(source=subnet_4, destination=subnet_2)
    factory.make_StaticRoute(source=subnet_4, destination=subnet_3)

    # Load builtin scripts in the database so we can generate fake results
    # below.
    load_builtin_scripts()

    hostname = gethostname()
    region_rack = get_one(
        Node.objects.filter(
            node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER, hostname=hostname
        )
    )
    # If "make run" executes before "make sampledata", the rack may have
    # already registered.
    if region_rack is None:
        region_rack = factory.make_Node(
            node_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            hostname=hostname,
            interface=False,
        )

        # Get list of mac addresses that should be used for the region
        # rack controller. This will make sure the RegionAdvertisingService
        # picks the correct region on first start-up and doesn't get multiple.
        mac_addresses = get_mac_addresses()

        def get_next_mac():
            try:
                return mac_addresses.pop()
            except IndexError:
                return factory.make_mac_address()

        # Region and rack controller (hostname of dev machine)
        #   eth0     - fabric 0 - untagged
        #   eth1     - fabric 0 - untagged
        #   eth2     - fabric 1 - untagged - 172.16.2.2/24 - static
        #   bond0    - fabric 0 - untagged - 172.16.1.2/24 - static
        #   bond0.10 - fabric 0 - 10       - 172.16.3.2/24 - static
        eth0 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth0",
            node=region_rack,
            vlan=fabric0_untagged,
            mac_address=get_next_mac(),
        )
        eth1 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth1",
            node=region_rack,
            vlan=fabric0_untagged,
            mac_address=get_next_mac(),
        )
        eth2 = factory.make_Interface(
            INTERFACE_TYPE.PHYSICAL,
            name="eth2",
            node=region_rack,
            vlan=fabric1_untagged,
            mac_address=get_next_mac(),
        )
        bond0 = factory.make_Interface(
            INTERFACE_TYPE.BOND,
            name="bond0",
            node=region_rack,
            vlan=fabric0_untagged,
            parents=[eth0, eth1],
            mac_address=eth0.mac_address,
        )
        bond0_10 = factory.make_Interface(
            INTERFACE_TYPE.VLAN,
            node=region_rack,
            vlan=fabric0_vlan10,
            parents=[bond0],
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="172.16.1.2",
            subnet=subnet_1,
            interface=bond0,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="172.16.2.2",
            subnet=subnet_2,
            interface=eth2,
        )
        factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY,
            ip="172.16.3.2",
            subnet=subnet_3,
            interface=bond0_10,
        )
        fabric0_untagged.primary_rack = region_rack
        fabric0_untagged.save()
        fabric1_untagged.primary_rack = region_rack
        fabric1_untagged.save()
        fabric0_vlan10.primary_rack = region_rack
        fabric0_vlan10.save()

    # Rack controller (happy-rack)
    #   eth0     - fabric 0 - untagged
    #   eth1     - fabric 0 - untagged
    #   eth2     - fabric 1 - untagged - 172.16.2.3/24 - static
    #   bond0    - fabric 0 - untagged - 172.16.1.3/24 - static
    #   bond0.10 - fabric 0 - 10       - 172.16.3.3/24 - static
    rack = factory.make_Node(
        node_type=NODE_TYPE.RACK_CONTROLLER,
        hostname="happy-rack",
        interface=False,
    )
    eth0 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, name="eth0", node=rack, vlan=fabric0_untagged
    )
    eth1 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, name="eth1", node=rack, vlan=fabric0_untagged
    )
    eth2 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL, name="eth2", node=rack, vlan=fabric1_untagged
    )
    bond0 = factory.make_Interface(
        INTERFACE_TYPE.BOND,
        name="bond0",
        node=rack,
        vlan=fabric0_untagged,
        parents=[eth0, eth1],
    )
    bond0_10 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, node=rack, vlan=fabric0_vlan10, parents=[bond0]
    )
    factory.make_StaticIPAddress(
        alloc_type=IPADDRESS_TYPE.STICKY,
        ip="172.16.1.3",
        subnet=subnet_1,
        interface=bond0,
    )
    factory.make_StaticIPAddress(
        alloc_type=IPADDRESS_TYPE.STICKY,
        ip="172.16.2.3",
        subnet=subnet_2,
        interface=eth2,
    )
    factory.make_StaticIPAddress(
        alloc_type=IPADDRESS_TYPE.STICKY,
        ip="172.16.3.3",
        subnet=subnet_3,
        interface=bond0_10,
    )
    fabric0_untagged.secondary_rack = rack
    fabric0_untagged.save()
    fabric1_untagged.secondary_rack = rack
    fabric1_untagged.save()
    fabric0_vlan10.secondary_rack = rack
    fabric0_vlan10.save()

    # Region controller (happy-region)
    #   eth0     - fabric 0 - untagged
    #   eth1     - fabric 0 - untagged
    #   eth2     - fabric 1 - untagged - 172.16.2.4/24 - static
    #   bond0    - fabric 0 - untagged - 172.16.1.4/24 - static
    #   bond0.10 - fabric 0 - 10       - 172.16.3.4/24 - static
    region = factory.make_Node(
        node_type=NODE_TYPE.REGION_CONTROLLER,
        hostname="happy-region",
        interface=False,
    )
    eth0 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL,
        name="eth0",
        node=region,
        vlan=fabric0_untagged,
    )
    eth1 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL,
        name="eth1",
        node=region,
        vlan=fabric0_untagged,
    )
    eth2 = factory.make_Interface(
        INTERFACE_TYPE.PHYSICAL,
        name="eth2",
        node=region,
        vlan=fabric1_untagged,
    )
    bond0 = factory.make_Interface(
        INTERFACE_TYPE.BOND,
        name="bond0",
        node=region,
        vlan=fabric0_untagged,
        parents=[eth0, eth1],
    )
    bond0_10 = factory.make_Interface(
        INTERFACE_TYPE.VLAN, node=region, vlan=fabric0_vlan10, parents=[bond0]
    )
    factory.make_StaticIPAddress(
        alloc_type=IPADDRESS_TYPE.STICKY,
        ip="172.16.1.4",
        subnet=subnet_1,
        interface=bond0,
    )
    factory.make_StaticIPAddress(
        alloc_type=IPADDRESS_TYPE.STICKY,
        ip="172.16.2.4",
        subnet=subnet_2,
        interface=eth2,
    )
    factory.make_StaticIPAddress(
        alloc_type=IPADDRESS_TYPE.STICKY,
        ip="172.16.3.4",
        subnet=subnet_3,
        interface=bond0_10,
    )

    # Create one machine for every status. Each machine has a random interface
    # and storage configration.
    node_statuses = [
        status
        for status in map_enum(NODE_STATUS).items()
        if status
        not in [NODE_STATUS.MISSING, NODE_STATUS.RESERVED, NODE_STATUS.RETIRED]
    ]
    machines = []
    test_scripts = [
        script.name
        for script in Script.objects.filter(script_type=SCRIPT_TYPE.TESTING)
    ]
    for _, status in node_statuses:
        owner = None
        if status in ALLOCATED_NODE_STATUSES:
            owner = random.choice([admin, user1, user2])
        elif status in [
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.FAILED_RELEASING,
        ]:
            owner = admin

        machine = factory.make_Node(
            status=status,
            owner=owner,
            zone=random.choice(zones),
            interface=False,
            with_boot_disk=False,
            power_type="manual",
            domain=random.choice(domains),
            memory=random.choice([1024, 4096, 8192]),
            description=random.choice(
                [
                    "",
                    "Scheduled for removeal",
                    "Firmware old",
                    "Earmarked for Project Fuse in April",
                ]
            ),
            cpu_count=random.randint(2, 8),
        )
        machine.set_random_hostname()
        machines.append(machine)

        # Create random network configuration.
        RandomInterfaceFactory.create_random(machine)

        # Add random storage devices and set a random layout.
        for _ in range(random.randint(1, 5)):
            factory.make_PhysicalBlockDevice(
                node=machine,
                size=random.randint(
                    LARGE_BLOCK_DEVICE, LARGE_BLOCK_DEVICE * 10
                ),
            )
        if status in [
            NODE_STATUS.READY,
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.DEPLOYING,
            NODE_STATUS.DEPLOYED,
            NODE_STATUS.FAILED_DEPLOYMENT,
            NODE_STATUS.RELEASING,
            NODE_STATUS.FAILED_RELEASING,
        ]:
            machine.set_storage_layout(
                random.choice(
                    [
                        layout
                        for layout in STORAGE_LAYOUTS.keys()
                        if layout != "vmfs6"
                    ]
                )
            )
            if status != NODE_STATUS.READY:
                machine._create_acquired_filesystems()

        # Add a random amount of events.
        for _ in range(random.randint(25, 100)):
            factory.make_Event(node=machine)

        # Add in commissioning and testing results.
        if status != NODE_STATUS.NEW:
            for _ in range(0, random.randint(1, 10)):
                css = ScriptSet.objects.create_commissioning_script_set(
                    machine
                )
                scripts = set()
                for __ in range(1, len(test_scripts)):
                    scripts.add(random.choice(test_scripts))
                tss = ScriptSet.objects.create_testing_script_set(
                    machine, list(scripts)
                )
            machine.current_commissioning_script_set = css
            machine.current_testing_script_set = tss
            machine.save()

        # Fill in historic results
        for script_set in machine.scriptset_set.all():
            if script_set in [css, tss]:
                continue
            for script_result in script_set:
                # Can't use script_result.store_result as it will try to
                # process the result and fail on the fake data.
                script_result.exit_status = random.randint(0, 255)
                if script_result.exit_status == 0:
                    script_result.status = SCRIPT_STATUS.PASSED
                else:
                    script_result.status = random.choice(
                        list(SCRIPT_STATUS_FAILED)
                    )
                script_result.started = factory.make_date()
                script_result.ended = script_result.started + timedelta(
                    seconds=random.randint(0, 10000)
                )
                script_result.stdout = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.stderr = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.output = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.save()

        # Only add in results in states where commissiong should be completed.
        if status not in [NODE_STATUS.NEW, NODE_STATUS.COMMISSIONING]:
            if status == NODE_STATUS.FAILED_COMMISSIONING:
                exit_status = random.randint(1, 255)
                script_status = random.choice(list(SCRIPT_STATUS_FAILED))
            else:
                exit_status = 0
                script_status = SCRIPT_STATUS.PASSED
            for script_result in css:
                # Can't use script_result.store_result as it will try to
                # process the result and fail on the fake data.
                script_result.status = script_status
                script_result.exit_status = exit_status
                script_result.started = factory.make_date()
                script_result.ended = script_result.started + timedelta(
                    seconds=random.randint(0, 10000)
                )
                script_result.stdout = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.stderr = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.output = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.save()
        elif status == NODE_STATUS.COMMISSIONING:
            for script_result in css:
                script_result.status = random.choice(
                    list(SCRIPT_STATUS_RUNNING_OR_PENDING)
                )
                if script_result.status != SCRIPT_STATUS.PENDING:
                    script_result.started = factory.make_date()
                script_result.save()

        # Only add in results in states where testing should be completed.
        if status not in [NODE_STATUS.NEW, NODE_STATUS.TESTING]:
            if status == NODE_STATUS.FAILED_TESTING:
                exit_status = random.randint(1, 255)
                script_status = random.choice(list(SCRIPT_STATUS_FAILED))
            else:
                exit_status = 0
                script_status = SCRIPT_STATUS.PASSED
            for script_result in tss:
                # Can't use script_result.store_result as it will try to
                # process the result and fail on the fake data.
                script_result.status = script_status
                script_result.exit_status = exit_status
                script_result.started = factory.make_date()
                script_result.ended = script_result.started + timedelta(
                    seconds=random.randint(0, 10000)
                )
                script_result.stdout = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.stderr = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.output = Bin(
                    factory.make_string().encode("utf-8")
                )
                script_result.save()
        elif status == NODE_STATUS.TESTING:
            for script_result in tss:
                script_result.status = random.choice(
                    list(SCRIPT_STATUS_RUNNING_OR_PENDING)
                )
                if script_result.status != SCRIPT_STATUS.PENDING:
                    script_result.started = factory.make_date()
                script_result.save()

        # Add installation results.
        if status in [
            NODE_STATUS.DEPLOYING,
            NODE_STATUS.DEPLOYED,
            NODE_STATUS.FAILED_DEPLOYMENT,
        ]:
            script_set = ScriptSet.objects.create_installation_script_set(
                machine
            )
            machine.current_installation_script_set = script_set
            machine.save()

        if status == NODE_STATUS.DEPLOYED:
            for script_result in machine.current_installation_script_set:
                stdout = factory.make_string().encode("utf-8")
                script_result.store_result(0, stdout)
        elif status == NODE_STATUS.FAILED_DEPLOYMENT:
            for script_result in machine.current_installation_script_set:
                exit_status = random.randint(1, 255)
                stdout = factory.make_string().encode("utf-8")
                stderr = factory.make_string().encode("utf-8")
                script_result.store_result(exit_status, stdout, stderr)

        # Add children devices to the deployed machine.
        if status == NODE_STATUS.DEPLOYED:
            boot_interface = machine.get_boot_interface()
            for _ in range(5):
                device = factory.make_Device(
                    interface=True,
                    domain=machine.domain,
                    parent=machine,
                    vlan=boot_interface.vlan,
                )
                device.set_random_hostname()
                RandomInterfaceFactory.assign_ip(
                    device.get_boot_interface(),
                    alloc_type=IPADDRESS_TYPE.STICKY,
                )

    # Create a few pods to and assign a random set of the machines to the pods.
    pods = [None]
    pod_storage_pools = defaultdict(list)
    machines_in_pods = defaultdict(list)
    for _ in range(3):
        subnet = random.choice(ipv4_subnets)
        ip = factory.pick_ip_in_Subnet(subnet)
        ip_address = factory.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.STICKY, ip=ip, subnet=subnet
        )
        power_address = "qemu+ssh://ubuntu@%s/system" % ip
        pod = factory.make_Pod(
            pod_type="virsh",
            parameters={"power_address": power_address},
            ip_address=ip_address,
            capabilities=[
                Capabilities.DYNAMIC_LOCAL_STORAGE,
                Capabilities.COMPOSABLE,
            ],
        )
        for _ in range(3):
            pool = factory.make_PodStoragePool(pod)
            pod_storage_pools[pod].append(pool)
        pod.default_storage_pool = pool
        pod.save()
        pods.append(pod)
    for machine in machines:
        # Add the machine to the pod if its lucky day!
        pod = random.choice(pods)
        if pod is not None:
            machine.bmc = pod
            machine.instance_power_parameters = {"power_id": machine.hostname}
            machine.save()
            machines_in_pods[pod].append(machine)

            vm = factory.make_VirtualMachine(
                identifier=machine.hostname,
                bmc=pod,
                machine=machine,
                unpinned_cores=machine.cpu_count,
            )

            # Assign the block devices on the machine to a storage pool.
            for block_device in machine.physicalblockdevice_set.all():
                factory.make_VirtualMachineDisk(
                    vm=vm,
                    name=block_device.name,
                    size=block_device.size,
                    backing_pool=random.choice(pod_storage_pools[pod]),
                )

    # Update the pod attributes so that it has more available then used.
    for pod in pods[1:]:
        used_resources = get_vm_host_used_resources(pod)
        pod.cores = used_resources.cores + random.randint(4, 8)
        pod.memory = used_resources.total_memory + random.choice(
            [1024, 2048, 4096, 4096 * 4, 4096 * 8]
        )
        pod.local_storage = sum(
            pool.storage for pool in pod_storage_pools[pod]
        )
        pod.save()

    # Create a few devices.
    for _ in range(10):
        device = factory.make_Device(interface=True)
        device.set_random_hostname()

    # Add some DHCP snippets.
    # - Global
    factory.make_DHCPSnippet(
        name="foo class",
        description="adds class for vender 'foo'",
        value=VersionedTextFile.objects.create(
            data=dedent(
                """\
            class "foo" {
                match if substring (
                    option vendor-class-identifier, 0, 3) = "foo";
            }
        """
            )
        ),
    )
    factory.make_DHCPSnippet(
        name="bar class",
        description="adds class for vender 'bar'",
        value=VersionedTextFile.objects.create(
            data=dedent(
                """\
            class "bar" {
                match if substring (
                    option vendor-class-identifier, 0, 3) = "bar";
            }
        """
            )
        ),
        enabled=False,
    )
    # - Subnet
    factory.make_DHCPSnippet(
        name="600 lease time",
        description="changes lease time to 600 secs.",
        value=VersionedTextFile.objects.create(data="default-lease-time 600;"),
        subnet=subnet_1,
    )
    factory.make_DHCPSnippet(
        name="7200 max lease time",
        description="changes max lease time to 7200 secs.",
        value=VersionedTextFile.objects.create(data="max-lease-time 7200;"),
        subnet=subnet_2,
        enabled=False,
    )
    # - Node
    factory.make_DHCPSnippet(
        name="boot from other server",
        description="instructs device to boot from other server",
        value=VersionedTextFile.objects.create(
            data=dedent(
                """\
            filename "test-boot";
            server-name "boot.from.me";
        """
            )
        ),
        node=device,
    )

    # Add notifications for admins, users, and each individual user, and for
    # each notification category.
    factory.make_Notification(
        "Attention admins! Core critical! Meltdown imminent! Evacuate "
        "habitat immediately!",
        admins=True,
        category="error",
    )
    factory.make_Notification(
        "Dear users, rumours of a core meltdown are unfounded. Please "
        "return to your home-pods and places of business.",
        users=True,
        category="warning",
    )
    factory.make_Notification(
        "FREE! For the next 2 hours get FREE blueberry and iodine pellets "
        "at the nutri-dispensers.",
        users=True,
        category="success",
    )
    for user in User.objects.all():
        context = {"name": user.username.capitalize()}
        factory.make_Notification(
            "Greetings, {name}! Get away from the habitat for the weekend and "
            "visit the Mare Nubium with MAAS Tours. Use the code METAL to "
            "claim a special gift!",
            user=user,
            context=context,
            category="info",
        )
