# Copyright 2012-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from datetime import datetime, timedelta
import hashlib
from io import BytesIO
from itertools import chain, repeat
import logging
import os
import random
import time
from typing import Dict, Iterable, List

from distro_info import UbuntuDistroInfo
from django.conf import settings
from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone
from netaddr import IPAddress, IPNetwork
import yaml

from maasserver.clusterrpc.driver_parameters import get_driver_types
from maasserver.enum import (
    ALLOCATED_NODE_STATUSES,
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    CACHE_MODE_TYPE,
    ENDPOINT_CHOICES,
    FILESYSTEM_FORMAT_TYPE_CHOICES,
    FILESYSTEM_GROUP_TYPE,
    FILESYSTEM_TYPE,
    INTERFACE_TYPE,
    IPADDRESS_TYPE,
    IPRANGE_TYPE,
    KEYS_PROTOCOL_TYPE,
    NODE_DEVICE_BUS,
    NODE_DEVICE_BUS_CHOICES,
    NODE_STATUS,
    NODE_TYPE,
    PARTITION_TABLE_TYPE,
    POWER_STATE,
    RDNS_MODE,
)
from maasserver.models import (
    BlockDevice,
    BootResource,
    BootResourceFile,
    BootResourceSet,
    BootSource,
    BootSourceCache,
    BootSourceSelection,
    CacheSet,
    Config,
    Device,
    DHCPSnippet,
    Discovery,
    DNSData,
    DNSResource,
    Domain,
    Event,
    EventType,
    Fabric,
    FileStorage,
    Filesystem,
    FilesystemGroup,
    ForwardDNSServer,
    IPRange,
    KeySource,
    LicenseKey,
    MDNS,
    Neighbour,
    Node,
    NodeDevice,
    NodeDeviceVPD,
    NodeMetadata,
    Notification,
    OwnerData,
    PackageRepository,
    Partition,
    PartitionTable,
    PhysicalBlockDevice,
    Pod,
    PodStoragePool,
    RegionController,
    RegionControllerProcess,
    RegionControllerProcessEndpoint,
    RegionRackRPCConnection,
    ResourcePool,
    RootKey,
    Script,
    ScriptResult,
    ScriptSet,
    Service,
    Space,
    SSHKey,
    SSLKey,
    StaticIPAddress,
    StaticRoute,
    Subnet,
    Tag,
    VersionedTextFile,
    VirtualBlockDevice,
    VLAN,
    VMCluster,
    VolumeGroup,
    Zone,
)
from maasserver.models.blockdevice import MIN_BLOCK_DEVICE_SIZE
from maasserver.models.bmc import BMC, BMCRoutableRackControllerRelationship
from maasserver.models.bootresourceset import XINSTALL_TYPES
from maasserver.models.interface import Interface, InterfaceRelationship
from maasserver.models.largefile import LargeFile
from maasserver.models.nodeconfig import NODE_CONFIG_TYPE, NodeConfig
from maasserver.models.numa import NUMANode, NUMANodeHugepages
from maasserver.models.partition import MIN_PARTITION_SIZE
from maasserver.models.rdns import RDNS
from maasserver.models.virtualmachine import VirtualMachine, VirtualMachineDisk
from maasserver.node_status import NODE_TRANSITIONS
from maasserver.secrets import SecretManager
from maasserver.sessiontimeout import SessionStore
from maasserver.storage_layouts import MIN_BOOT_PARTITION_SIZE
from maasserver.testing import get_data
from maasserver.testing.testclient import MAASSensibleRequestFactory
from maasserver.utils.bootresource import LocalBootResourceFile
from maasserver.utils.converters import round_size_to_nearest_block
from maasserver.utils.orm import get_one, reload_object
from maasserver.utils.osystems import get_release_from_distro_info
from maasserver.worker_user import get_worker_user
import maastesting.factory
from maastesting.factory import TooManyRandomRetries
from metadataserver.builtin_scripts import load_builtin_scripts
from metadataserver.enum import (
    HARDWARE_TYPE,
    HARDWARE_TYPE_CHOICES,
    RESULT_TYPE,
    RESULT_TYPE_CHOICES,
    SCRIPT_PARALLEL_CHOICES,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
    SCRIPT_STATUS_RUNNING,
    SCRIPT_TYPE,
    SCRIPT_TYPE_CHOICES,
)
from metadataserver.fields import Bin
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.security import to_hex
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.network import inet_ntop

# We have a limited number of public keys:
# src/maasserver/tests/data/test_rsa{0, 1, 2, 3, 4}.pub
MAX_PUBLIC_KEYS = 5

# Used to save a node without worrying about a valid transition.
ALL_NODE_STATES = list(map_enum(NODE_STATUS).values())

# Maximum PID available on this machine.
with open("/proc/sys/kernel/pid_max") as fd:
    PID_MAX = int(fd.read())

# Use `undefined` instead of `None` for default factory arguments when `None`
# is a reasonable value for the argument.
undefined = object()

# Use `RANDOM` instead of `None` for default factory arguments when `None`
# is a reasonable value for the argument and a random value is desired.
RANDOM = object()


# Use `RANDOM_OR_NONE` instead of `None` for default factory arguments when
# `None` is a reasonable value for the argument and a random value /or/ None is
# desired.
RANDOM_OR_NONE = object()


class Factory(maastesting.factory.Factory):
    def make_fake_request(
        self, path="/", method="GET", cookies=None, data=None
    ):
        """Create a fake request.

        :param path: The path to which to make the request.
        :param method: The method to use for the request
            ('GET' or 'POST').
        :param cookies: Optional `dict` with the cookies for the request.
        :param data: Optional `dict` of parameters.
        """
        rf = MAASSensibleRequestFactory()
        if data is None:
            data = {}
        if cookies is None:
            cookies = {}
        if method == "GET":
            request = rf.get(path, data=data)
        elif method == "POST":
            request = rf.post(path, data=data)
        else:
            request = rf.get(path, data=data)
            request.method = method
        request.data = data
        request.COOKIES = cookies.copy()
        return request

    def make_file_upload(self, name=None, content=None):
        """Create a file-like object for upload in http POST or PUT.

        To upload a file using the Django test client, just include a
        parameter that maps not to a string, but to a file upload as
        produced by this method.

        :param name: Name of the file to be uploaded.  If omitted, one will
            be made up.
        :type name: `unicode`
        :param content: Contents for the uploaded file.  If omitted, some
            contents will be made up.
        :type content: `bytes`
        :return: A file-like object, with the requested `content` and `name`.
        """
        if content is None:
            content = self.make_string().encode(settings.DEFAULT_CHARSET)
        if name is None:
            name = self.make_name("file")
        assert isinstance(content, bytes)
        upload = BytesIO(content)
        upload.name = name
        return upload

    def pick_power_type(self, but_not=None):
        """Pick a random power type and return it.

        :param but_not: Exclude these values from result
        :type but_not: Sequence
        """
        if but_not is None:
            but_not = []
        but_not.append("")
        return random.choice(
            [choice for choice in get_driver_types() if choice not in but_not]
        )

    def pick_commissioning_release(self, osystem):
        """Pick a random commissioning release from operating system."""
        releases = osystem.get_supported_commissioning_releases()
        return random.choice(releases)

    def pick_ubuntu_release(self, but_not=None):
        """Pick a random supported Ubuntu release.

        :param but_not: Exclude these releases from the result
        :type but_not: Sequence
        """
        ubuntu_releases = UbuntuDistroInfo()
        supported_releases = ubuntu_releases.all[
            ubuntu_releases.all.index("precise") :
        ]
        if but_not is None:
            but_not = []
        return random.choice(
            [choice for choice in supported_releases if choice not in but_not]
        )

    def make_script_content(
        self,
        yaml_content=None,
        shebang="/bin/bash",
        version="1.0",
        content=None,
    ):
        script = "#!%s\n\n" % shebang
        if yaml_content is not None:
            script += "# --- Start MAAS %s script metadata ---\n" % version
            if isinstance(yaml_content, dict):
                script += "# %s" % yaml.safe_dump(yaml_content).replace(
                    "\n", "\n# "
                )
            else:
                script += yaml_content
            script += "\n# --- End MAAS %s script metadata ---\n" % version
        if content is None:
            script += factory.make_string()
        else:
            script += content
        return script

    def _save_node_unchecked(self, node):
        """Save a :class:`Node`, but circumvent status transition checks."""
        valid_initial_states = NODE_TRANSITIONS[None]
        NODE_TRANSITIONS[None] = ALL_NODE_STATES
        try:
            node.save()
        finally:
            NODE_TRANSITIONS[None] = valid_initial_states

    def make_Device(
        self,
        hostname=None,
        interface=False,
        domain=None,
        vlan=None,
        fabric=None,
        owner_data={},
        **kwargs,
    ):
        if hostname is None:
            hostname = self.make_string(20)
        if domain is None:
            domain = Domain.objects.get_default_domain()
        power_type = kwargs.pop("power_type", None)
        power_params = kwargs.pop("power_param", {})
        device = Device(hostname=hostname, domain=domain, **kwargs)
        if power_type is not None:
            device.set_power_config(power_type, power_params)
        device.save()
        # Add owner data.
        OwnerData.objects.set_owner_data(device, owner_data)
        if interface:
            self.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=device, vlan=vlan, fabric=fabric
            )
        return reload_object(device)

    # PIDs for use with make_RegionControllerProcess. Note that the simpler
    # cycle(range(...)) is not used because it gradually consumes all memory.
    _rcp_pids = chain.from_iterable(repeat(range(PID_MAX)))

    def make_RegionControllerProcess(
        self, region=None, pid=None, updated=None
    ):
        if region is None:
            region = self.make_RegionController()
        if pid is None:
            pid = next(self._rcp_pids)
        process = RegionControllerProcess(
            region=region, pid=pid, updated=updated
        )
        process.save()
        return process

    # Ports for use with make_RegionControllerProcessEndpoint. Note that the
    # simpler cycle(range(...)) is not used because it gradually consumes all
    # memory.
    _rcpe_ports = chain.from_iterable(repeat(range(2**16)))

    def make_RegionControllerProcessEndpoint(
        self, process=None, address=None, port=None
    ):
        if process is None:
            process = self.make_RegionControllerProcess()
        if address is None:
            address = self.make_ip_address()
        if port is None:
            port = next(self._rcpe_ports)
        endpoint = RegionControllerProcessEndpoint(
            process=process, address=address, port=port
        )
        endpoint.save()
        return endpoint

    def make_RegionRackRPCConnection(
        self, rack_controller=None, endpoint=None
    ):
        if rack_controller is None:
            rack_controller = self.make_RackController()
        if endpoint is None:
            endpoint = self.make_RegionControllerProcessEndpoint()
        conn = RegionRackRPCConnection(
            rack_controller=rack_controller, endpoint=endpoint
        )
        conn.save()
        return conn

    def make_Node(
        self,
        interface=False,
        hostname=None,
        domain=None,
        status=None,
        architecture="i386/generic",
        description=None,
        min_hwe_kernel=None,
        hwe_kernel=None,
        node_type=NODE_TYPE.MACHINE,
        updated=None,
        created=None,
        zone=None,
        networks=None,
        sortable_name=False,
        power_type="virsh",
        power_parameters=None,
        power_state=None,
        power_state_updated=undefined,
        with_boot_disk=True,
        vlan=None,
        fabric=None,
        bmc_connected_to=None,
        owner_data={},
        hardware_uuid=None,
        with_empty_script_sets=False,
        bmc=None,
        ephemeral_deploy=False,
        enable_hw_sync=False,
        parent=None,
        **kwargs,
    ):
        """Make a :class:`Node`.

        :param sortable_name: If `True`, use a that will sort consistently
            between different collation orders.  Use this when testing sorting
            by name, where the database and the python code may have different
            ideas about collation orders, especially when it comes to case
            differences.
        :param bmc_connected_to: Assign an IP address to the BMC for this node
            so this rack controller can control the power.
        :type bmc_connected_to: `:class:RackController`
        """
        # hostname=None is a valid value, hence the set_hostname trick.
        if hostname is None:
            hostname = self.make_string(20)
        if domain is None:
            domain = Domain.objects.get_default_domain()
        if description is None:
            description = ""
        if sortable_name:
            hostname = hostname.lower()
        if status is None:
            status = NODE_STATUS.DEFAULT
        if zone is None:
            zone = Zone.objects.get_default_zone()
        if power_state is None:
            power_state = self.pick_enum(POWER_STATE)
        if power_state_updated is undefined:
            power_state_updated = timezone.now() - timedelta(
                minutes=random.randint(0, 15)
            )
        if hardware_uuid is None:
            hardware_uuid = factory.make_UUID()
        node = Node(
            hostname=hostname,
            status=status,
            architecture=architecture,
            min_hwe_kernel=min_hwe_kernel,
            hwe_kernel=hwe_kernel,
            node_type=node_type,
            zone=zone,
            description=description,
            power_state=power_state,
            power_state_updated=power_state_updated,
            domain=domain,
            bmc=bmc,
            hardware_uuid=hardware_uuid,
            ephemeral_deploy=ephemeral_deploy,
            enable_hw_sync=enable_hw_sync,
            cpu_speed=random.randint(1000, 5000),
            parent=parent,
            **kwargs,
        )
        if bmc is None and power_type:
            # These setters will overwrite the BMC, so don't use them if the
            # BMC was specified.
            node.set_power_config(power_type, power_parameters or {})
        self._save_node_unchecked(node)
        # We do not generate random networks by default because the limited
        # number of VLAN identifiers (4,094) makes it very likely to
        # encounter collisions.
        if networks is not None:
            node.networks.add(*networks)
        if interface:
            self.make_Interface(
                INTERFACE_TYPE.PHYSICAL, node=node, vlan=vlan, fabric=fabric
            )
        if node_type == NODE_TYPE.MACHINE and with_boot_disk:
            root_partition = self.make_Partition(
                node=node, block_device_size=MIN_BOOT_PARTITION_SIZE
            )
            acquired = node.status in ALLOCATED_NODE_STATUSES
            if node.osystem in ["centos", "rhel"]:
                # CentOS and RHEL do not support Bcache or ZFS so don't create
                # a node using those filesystems if the caller told us the
                # osystem is CentOS or RHEL.
                fstype = self.pick_filesystem_type(
                    (
                        FILESYSTEM_TYPE.BCACHE_BACKING,
                        FILESYSTEM_TYPE.BCACHE_CACHE,
                        FILESYSTEM_TYPE.ZFSROOT,
                    )
                )
            else:
                fstype = self.pick_filesystem_type()
            self.make_Filesystem(
                fstype=fstype,
                partition=root_partition,
                mount_point="/",
                acquired=acquired,
            )
            node.boot_disk = root_partition.partition_table.block_device
            node.save()

        # Setup the BMC connected to rack controller if a BMC is created.
        if bmc_connected_to is not None:
            if power_type != "virsh":
                raise Exception(
                    "bmc_connected_to requires that power_type set to 'virsh'"
                )
            rack_interface = bmc_connected_to.get_boot_interface()
            if rack_interface is None:
                rack_interface = self.make_Interface(
                    INTERFACE_TYPE.PHYSICAL, node=bmc_connected_to
                )
            existing_static_ips = [
                ip_address
                for ip_address in rack_interface.ip_addresses.filter(
                    alloc_type__in=[
                        IPADDRESS_TYPE.AUTO,
                        IPADDRESS_TYPE.STICKY,
                    ],
                    subnet__isnull=False,
                    ip__isnull=False,
                )
                if ip_address.ip
            ]
            if len(existing_static_ips) == 0:
                network = factory.make_ipv4_network()
                subnet = self.make_Subnet(
                    cidr=str(network.cidr), vlan=rack_interface.vlan
                )
                ip_address = self.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip=self.pick_ip_in_Subnet(subnet),
                    subnet=subnet,
                    interface=rack_interface,
                )
            else:
                ip_address = existing_static_ips[0]
            bmc_ip_address = self.pick_ip_in_Subnet(ip_address.subnet)
            power_params = {
                **node.get_power_parameters(),
                "power_address": "qemu+ssh://user@%s/system"
                % (factory.ip_to_url_format(bmc_ip_address)),
                "power_id": factory.make_name("power_id"),
            }
            node.set_power_config("virsh", power_params)
            node.save()

        # Add owner data.
        OwnerData.objects.set_owner_data(node, owner_data)

        if with_empty_script_sets:
            # Make sure base scripts are loaded into the database.
            load_builtin_scripts()

            commissioning_script_set = (
                ScriptSet.objects.create_commissioning_script_set(node)
            )
            node.current_commissioning_script_set = commissioning_script_set

            # Create a testing script to create a ScriptResult for
            script = factory.make_Script(script_type=SCRIPT_TYPE.TESTING)
            testing_script_set = ScriptSet.objects.create_testing_script_set(
                node, scripts=[script.name]
            )
            node.current_testing_script_set = testing_script_set

            installation_script_set = (
                ScriptSet.objects.create_installation_script_set(node)
            )
            node.current_installation_script_set = installation_script_set

            release_script_set = ScriptSet.objects.create_release_script_set(
                node
            )
            release_script_set.save()
            node.current_release_script_set = release_script_set

            node.save()
        # Update the 'updated'/'created' fields with a call to 'update'
        # preventing a call to save() from overriding the values.
        if updated is not None:
            Node.objects.filter(id=node.id).update(updated=updated)
        if created is not None:
            Node.objects.filter(id=node.id).update(created=created)
        return reload_object(node)

    def make_Machine(self, *args, **kwargs):
        machine = self.make_Node(*args, node_type=NODE_TYPE.MACHINE, **kwargs)
        return machine.as_machine()

    def make_Controller(
        self,
        controller_type=None,
        hostname=None,
        last_image_sync=undefined,
        owner=None,
        zone=None,
        dynamic=True,
        status=NODE_STATUS.DEPLOYED,
        subnet=None,
        vlan=None,
        ifname=None,
        interface=None,
        url="",
        bmc=None,
        managing_process=None,
    ):
        if controller_type is None:
            controller_type = random.choice(
                [
                    NODE_TYPE.REGION_CONTROLLER,
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                ]
            )
        if hostname is None:
            hostname = self.make_string(prefix="controller")
        if owner is None:
            owner = get_worker_user()
        node = self.make_Node_with_Interface_on_Subnet(
            node_type=controller_type,
            hostname=hostname,
            owner=owner,
            dynamic=dynamic,
            status=status,
            with_dhcp_rack_primary=False,
            with_dhcp_rack_secondary=False,
            subnet=subnet,
            vlan=vlan,
            ifname=ifname,
            interface=interface,
            url=url,
            managing_process=managing_process,
            zone=zone,
        )
        node.bmc = bmc
        if last_image_sync is undefined:
            node.last_image_sync = timezone.now() - timedelta(
                minutes=random.randint(1, 15)
            )
        else:
            node.last_image_sync = last_image_sync
        node.save()
        return node

    def make_RegionController(self, *args, **kwargs):
        return self.make_Controller(
            *args, controller_type=NODE_TYPE.REGION_CONTROLLER, **kwargs
        ).as_region_controller()

    def make_RackController(self, *args, **kwargs):
        return self.make_Controller(
            *args, controller_type=NODE_TYPE.RACK_CONTROLLER, **kwargs
        ).as_rack_controller()

    def make_RegionRackController(self, *args, **kwargs):
        return self.make_Controller(
            *args,
            controller_type=NODE_TYPE.REGION_AND_RACK_CONTROLLER,
            **kwargs,
        ).as_rack_controller()

    def make_rack_with_interfaces(self, **interfaces: Dict[str, List[str]]):
        """Create a rack controller that has the given interfaces.

        The interfaces dict has the interface name as the key and a list
        of IP addresses with network mask as the value. For example:
           {"eth0": ["10.10.10.10/24"]}

        The subnets for the IPs need to exist when calling this method.
        """
        rack = factory.make_Node(
            node_type=random.choice(
                [
                    NODE_TYPE.RACK_CONTROLLER,
                    NODE_TYPE.REGION_AND_RACK_CONTROLLER,
                ]
            ),
        )
        for name, ips in interfaces.items():
            interface = None
            for ip in ips:
                cidr = IPNetwork(ip).cidr
                subnet = Subnet.objects.get(cidr=cidr)
                if interface is None:
                    interface = factory.make_Interface(
                        node=rack,
                        name=name,
                        vlan=subnet.vlan,
                    )
                assert subnet.vlan == interface.vlan
                factory.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip=ip.split("/")[0],
                    subnet=subnet,
                    interface=interface,
                )
        return rack

    def make_BMC(
        self, power_type=None, power_parameters=None, ip_address=None, **kwargs
    ):
        """Make a :class:`BMC`."""
        # If an IP address was specified, we need to present it in the BMC
        # power_parameters, or it will be overwritten.
        if ip_address is not None:
            if power_type is None:
                power_type = "ipmi"
            if power_parameters is None:
                power_parameters = {"power_address": ip_address.ip}
        if power_type is None:
            power_type = "manual"
        if power_parameters is None:
            power_parameters = {}
        bmc = BMC(
            power_type=power_type,
            power_parameters=power_parameters,
            ip_address=ip_address,
            **kwargs,
        )
        bmc.save()
        return bmc

    def make_NodeMetadata(self, node=None, key=None, value=None, **kwargs):
        if node is None:
            owner = get_worker_user()
            node = self.make_Node(
                owner=owner, node_type=NODE_TYPE.MACHINE, **kwargs
            )
            node.save()

        if key is None:
            key = self.make_name("key")
        if value is None:
            value = self.make_string(prefix="value", spaces=True)
        metadata = NodeMetadata(node=node, key=key, value=value)
        metadata.save()
        return metadata

    def make_Pod(
        self,
        pod_type=None,
        parameters=None,
        ip_address=None,
        host=None,
        project=None,
        cluster=None,
        **kwargs,
    ):
        if pod_type is None:
            pod_type = "virsh"
        if parameters is None:
            parameters = {}
            if ip_address is not None:
                ip = str(ip_address.ip)
            else:
                ip = self.make_ip_address()
            if ":" in ip:
                ip = "[%s]" % ip
            if pod_type == "virsh":
                parameters = {"power_address": f"qemu+ssh://{ip}/system"}
            elif pod_type == "lxd":
                parameters = {"power_address": f"{ip}:8443"}
        if project:
            parameters["project"] = project
        pod = Pod(
            power_type=pod_type,
            power_parameters=parameters,
            ip_address=ip_address,
            **kwargs,
        )
        pod.save()

        if host is not None:
            pod.hints.nodes.add(host)
        if cluster is not None:
            pod.hints.cluster = cluster
            pod.hints.save()

        return pod

    def make_Domain(self, name=None, ttl=None, authoritative=True):
        if name is None:
            name = self.make_name("domain")
        domain = Domain(name=name, ttl=ttl, authoritative=authoritative)
        domain.save()
        return domain

    def make_ForwardDNSServer(self, ip_address=None, domains=None):
        if ip_address is None:
            ip_address = self.make_ip_address()
        fwd_dns_srvr = ForwardDNSServer(ip_address=ip_address)
        fwd_dns_srvr.save()
        fwd_dns_srvr.domains.set(domains)
        fwd_dns_srvr.save()
        return fwd_dns_srvr

    def pick_rrset(self, rrtype=None, rrdata=None, exclude=[]):
        while rrtype is None:
            rrtype = self.pick_choice(
                (
                    ("CNAME", "Canonical name"),
                    ("MX", "Mail Exchanger"),
                    ("NS", "Name Server"),
                    # We don't autogenerate SRV, because of NAME.
                    # ('SRV', "Service"),
                    ("SSHFP", "SSH Fingerprint"),
                    ("TXT", "Text"),
                )
            )
            if rrtype in exclude:
                rrtype = None
            # Force data appropriate to the (random) RRType.
            rrdata = None
        rrtype = rrtype.upper()
        if rrdata is None:
            if rrtype == "CNAME" or rrtype == "NS":
                rrdata = "%s" % self.make_name(rrtype.lower())
            elif rrtype == "MX":
                rrdata = "%d %s" % (
                    random.randint(0, 65535),
                    self.make_name("mx"),
                )
            elif rrtype == "SSHFP":
                algo = random.randint(1, 4)
                fptype = random.randint(1, 2)
                if fptype == 1:
                    fp = hashlib.sha1()
                elif fptype == 2:
                    fp = hashlib.sha256()
                # Add other types as needed.
                fp.update(factory.make_name("sshfp").encode("ASCII"))
                rrdata = "%d %d %s" % (algo, fptype, fp.digest())
            elif rrtype == "SRV":
                raise ValueError("No automatic generation of SRV DNSData")
            elif rrtype == "TXT":
                rrdata = self.make_name(size=random.randint(100, 65535))
            else:
                rrdata = self.make_name("dnsdata")
        return (rrtype, rrdata)

    def make_DNSData(
        self, dnsresource=None, rrtype=None, rrdata=None, ttl=None, **kwargs
    ):
        # If they didn't pass in an ip_addresses, suppress them.
        if "ip_addresses" not in kwargs:
            kwargs["no_ip_addresses"] = True
            exclude = []
        else:
            exclude = ["CNAME"]
        if rrtype is None or rrdata is None:
            if dnsresource is not None and dnsresource.ip_addresses.exists():
                exclude = ["CNAME"]
            (rrtype, rrdata) = self.pick_rrset(rrtype, rrdata, exclude=exclude)
        if dnsresource is None:
            dnsresource = self.make_DNSResource(**kwargs)
        dnsdata = DNSData(
            dnsresource=dnsresource, ttl=ttl, rrtype=rrtype, rrdata=rrdata
        )
        dnsdata.save()
        return dnsdata

    def make_DNSResource(
        self,
        domain=None,
        ip_addresses=None,
        name=None,
        address_ttl=None,
        no_ip_addresses=False,
        **kwargs,
    ):
        if "name" in kwargs:
            name = kwargs["name"]
            del kwargs["name"]
        if "domain" in kwargs:
            domain = kwargs["domain"]
            del kwargs["domain"]
        if "address_ttl" in kwargs:
            address_ttl = kwargs["address_ttl"]
            del kwargs["address_ttl"]
        if domain is None:
            domain = self.make_Domain()
        if name is None:
            name = self.make_name("label")
        if ip_addresses is None and not no_ip_addresses:
            ip_addresses = [self.make_StaticIPAddress(**kwargs)]
        elif isinstance(ip_addresses, list):
            ip_addresses = [
                self.make_StaticIPAddress(
                    ip=ip, alloc_type=IPADDRESS_TYPE.USER_RESERVED
                )
                if not isinstance(ip, StaticIPAddress)
                else ip
                for ip in ip_addresses
            ]
        dnsrr, _ = DNSResource.objects.get_or_create(
            name=name, address_ttl=address_ttl, domain=domain
        )
        dnsrr.save()
        if ip_addresses:
            dnsrr.ip_addresses.set(ip_addresses)
            dnsrr.save(force_update=True)
        return dnsrr

    def make_Script(
        self,
        name=None,
        title=None,
        description=None,
        tags=None,
        script_type=None,
        hardware_type=None,
        parallel=None,
        timeout=None,
        destructive=False,
        default=False,
        script=None,
        may_reboot=None,
        recommission=None,
        for_hardware=None,
        apply_configured_networking=False,
        **kwargs,
    ):
        if for_hardware is None:
            for_hardware = []
        if name is None:
            name = self.make_name("name")
        if title is None:
            title = self.make_name("title")
        if description is None:
            description = self.make_string()
        if tags is None:
            tags = [factory.make_name("tag") for _ in range(3)]
        if script_type is None:
            script_type = self.pick_choice(SCRIPT_TYPE_CHOICES)
        if hardware_type is None:
            hardware_type = self.pick_choice(HARDWARE_TYPE_CHOICES)
        if parallel is None:
            parallel = self.pick_choice(SCRIPT_PARALLEL_CHOICES)
        if timeout is None:
            timeout = timedelta(seconds=random.randint(0, 600))
        if may_reboot is None:
            may_reboot = factory.pick_bool()
        if recommission and script_type == SCRIPT_TYPE.COMMISSIONING:
            recommission = factory.pick_bool()
        else:
            recommission = False
        if script is None:
            script = VersionedTextFile.objects.create(
                data=self.make_script_content()
            )
        return Script.objects.create(
            name=name,
            title=title,
            description=description,
            tags=tags,
            script_type=script_type,
            hardware_type=hardware_type,
            parallel=parallel,
            timeout=timeout,
            destructive=destructive,
            default=default,
            script=script,
            may_reboot=may_reboot,
            recommission=recommission,
            for_hardware=for_hardware,
            apply_configured_networking=apply_configured_networking,
            **kwargs,
        )

    def make_ScriptSet(self, last_ping=None, node=None, result_type=None):
        if last_ping is None:
            last_ping = datetime.now()
        if node is None:
            node = self.make_Node()
        if result_type is None:
            result_type = self.pick_choice(RESULT_TYPE_CHOICES)
        return ScriptSet.objects.create(
            last_ping=last_ping, node=node, result_type=result_type
        )

    def make_ScriptResult(
        self,
        script_set=None,
        script=None,
        script_version=None,
        status=None,
        exit_status=None,
        script_name=None,
        output=None,
        stdout=None,
        stderr=None,
        result=None,
        started=None,
        ended=None,
        suppressed=False,
        **kwargs,
    ):
        if script_set is None:
            if script is not None:
                script_set_type = (
                    RESULT_TYPE.TESTING
                    if script.script_type == SCRIPT_TYPE.TESTING
                    else RESULT_TYPE.COMMISSIONING
                )
            else:
                script_set_type = None
            script_set = self.make_ScriptSet(result_type=script_set_type)
        if script is None and script_name is None:
            if script_set.result_type == RESULT_TYPE.COMMISSIONING:
                script = self.make_Script(
                    script_type=SCRIPT_TYPE.COMMISSIONING
                )
            else:
                script = self.make_Script(script_type=SCRIPT_TYPE.TESTING)
        if script is not None:
            script_name = script.name
        if status is None:
            status = self.pick_choice(SCRIPT_STATUS_CHOICES)
        if status == SCRIPT_STATUS.PENDING:
            # Pending results shouldn't have results stored.
            if output is None:
                output = b""
            if stdout is None:
                stdout = b""
            if stderr is None:
                stderr = b""
            if result is None:
                result = b""
        else:
            if exit_status is None:
                exit_status = random.randint(0, 255)
            if output is None:
                output = self.make_string().encode("utf-8")
            if stdout is None:
                stdout = self.make_string().encode("utf-8")
            if stderr is None:
                stderr = self.make_string().encode("utf-8")
            if result is None:
                result = yaml.safe_dump(
                    {
                        "results": {
                            self.make_name("key"): self.make_name("value")
                        }
                    }
                ).encode("utf-8")
            if script_version is None and script_name is None:
                script_version = script.script
            if started is None:
                started = datetime.now() - timedelta(
                    seconds=random.randint(1, 500)
                )
            if ended is None and status not in SCRIPT_STATUS_RUNNING:
                ended = datetime.now()
        return ScriptResult.objects.create(
            script_set=script_set,
            script=script,
            script_version=script_version,
            status=status,
            exit_status=exit_status,
            script_name=script_name,
            output=Bin(output),
            stdout=Bin(stdout),
            stderr=Bin(stderr),
            result=Bin(result),
            started=started,
            ended=ended,
            suppressed=suppressed,
            **kwargs,
        )

    def make_Node_with_Interface_on_Subnet(
        self,
        interface_count=1,
        vlan=None,
        subnet=None,
        cidr=None,
        ip_address=None,
        fabric=None,
        ifname=None,
        extra_ifnames=None,
        unmanaged=False,
        with_dhcp_rack_primary=True,
        with_dhcp_rack_secondary=False,
        primary_rack=None,
        secondary_rack=None,
        link_connected=True,
        interface_speed=None,
        link_speed=None,
        **kwargs,
    ):
        """Create a Node that has a Interface which is on a Subnet.

        :param interface_count: count of interfaces to add
        :param **kwargs: Additional parameters to pass to make_Node.
        """
        mac_address = None
        iftype = INTERFACE_TYPE.PHYSICAL
        if "address" in kwargs:
            mac_address = kwargs["address"]
            del kwargs["address"]
        if "iftype" in kwargs:
            iftype = kwargs["iftype"]
            del kwargs["iftype"]
        if "ip_version" in kwargs and cidr is None:
            ip_version = kwargs.pop("ip_version")
        else:
            ip_version = None
        node = self.make_Node(fabric=fabric, **kwargs)
        if vlan is None and subnet is not None:
            vlan = subnet.vlan
        if vlan is None:
            if fabric is None:
                fabric = factory.make_Fabric()
            vlan = fabric.get_default_vlan()
            dhcp_on = with_dhcp_rack_primary or with_dhcp_rack_secondary
            vlan.dhcp_on = dhcp_on
            vlan.save()
        if subnet is None:
            subnet = self.make_Subnet(vlan=vlan, cidr=cidr, version=ip_version)
        boot_interface = self.make_Interface(
            iftype,
            name=ifname,
            node=node,
            vlan=vlan,
            mac_address=mac_address,
            link_connected=link_connected,
            interface_speed=interface_speed,
            link_speed=link_speed,
        )
        node.boot_interface = boot_interface
        node.save()

        self.make_StaticIPAddress(
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
            ip="",
            subnet=subnet,
            interface=boot_interface,
        )
        should_have_default_link_configuration = node.status not in [
            NODE_STATUS.NEW,
            NODE_STATUS.COMMISSIONING,
            NODE_STATUS.FAILED_COMMISSIONING,
        ] or node.node_type in [
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ]
        if should_have_default_link_configuration:
            self.make_StaticIPAddress(
                alloc_type=(
                    IPADDRESS_TYPE.STICKY
                    if ip_address
                    else IPADDRESS_TYPE.AUTO
                ),
                ip=ip_address if ip_address else "",
                subnet=subnet,
                interface=boot_interface,
            )
        for _ in range(1, interface_count):
            ifname = None
            if extra_ifnames:
                ifname = extra_ifnames[0]
                extra_ifnames = extra_ifnames[1:]
            interface = self.make_Interface(
                INTERFACE_TYPE.PHYSICAL,
                name=ifname,
                node=node,
                vlan=vlan,
                link_connected=link_connected,
                interface_speed=interface_speed,
                link_speed=link_speed,
            )
            self.make_StaticIPAddress(
                alloc_type=IPADDRESS_TYPE.DISCOVERED,
                ip="",
                subnet=subnet,
                interface=interface,
            )
            if should_have_default_link_configuration:
                self.make_StaticIPAddress(
                    alloc_type=IPADDRESS_TYPE.STICKY,
                    ip="",
                    subnet=subnet,
                    interface=interface,
                )
        if with_dhcp_rack_primary:
            if primary_rack is None:
                if vlan.primary_rack is None:
                    primary_rack = self.make_RackController(
                        vlan=vlan, subnet=subnet
                    )
                else:
                    primary_rack = vlan.primary_rack
            vlan.primary_rack = primary_rack
            vlan.save()
        if with_dhcp_rack_secondary:
            if secondary_rack is None:
                if vlan.secondary_rack is None:
                    secondary_rack = self.make_RackController(
                        vlan=vlan, subnet=subnet
                    )
                else:
                    secondary_rack = vlan.secondary_rack
            vlan.secondary_rack = secondary_rack
            vlan.save()
        return reload_object(node)

    def make_Machine_with_Interface_on_Subnet(self, *args, **kwargs):
        machine = self.make_Node_with_Interface_on_Subnet(
            *args, node_type=NODE_TYPE.MACHINE, **kwargs
        )
        return machine.as_machine()

    def _get_exclude_list(self, subnet):
        ip_addresses = [
            IPAddress(ip)
            for ip in StaticIPAddress.objects.filter(
                subnet=subnet
            ).values_list("ip", flat=True)
            if ip is not None
        ]
        if subnet.gateway_ip is not None:
            ip_addresses.append(IPAddress(subnet.gateway_ip))
        return ip_addresses

    def make_StaticIPAddress(
        self,
        ip=undefined,
        alloc_type=IPADDRESS_TYPE.AUTO,
        interface=None,
        user=None,
        subnet=None,
        dnsresource=None,
        cidr=None,
        hostname=None,
        **kwargs,
    ):
        """Create and return a StaticIPAddress model object.

        If a non-None `interface` is passed, connect this IP address to the
        given interface.
        """
        vlan = None if interface is None else interface.vlan

        if cidr is None:
            if subnet is None:
                if vlan is None:
                    subnet = Subnet.objects.first()
                else:
                    subnet = Subnet.objects.filter(vlan=vlan).first()
            # Create a subnet if the allocation type is not USER_RESERVED.
            # It's not super clear why this is necessary, but it is thought
            # that in ages past (?) MAAS did not require a network to be
            # modelled in order to add a USER_RESERVED address, and there are
            # most likely test cases that depend on this behavior.
            if (
                ip is undefined
                and subnet is None
                and alloc_type != IPADDRESS_TYPE.USER_RESERVED
            ):
                subnet = self.make_Subnet(vlan=vlan)
        else:
            if vlan is None:
                subnet = get_one(Subnet.objects.filter(cidr=cidr))
            else:
                subnet = get_one(Subnet.objects.filter(cidr=cidr, vlan=vlan))
            if subnet is None:
                subnet = self.make_Subnet(cidr=cidr, vlan=vlan)

        if ip is undefined:
            # See the above comment about subnets and USER_RESERVED for some
            # hints as to why we think this behaviour exists.
            if not subnet and alloc_type == IPADDRESS_TYPE.USER_RESERVED:
                ip = self.make_ip_address()
            elif subnet is not None:
                ip = self.pick_ip_in_network(
                    IPNetwork(subnet.cidr),
                    but_not=self._get_exclude_list(subnet),
                )
        elif ip is None or ip == "":
            ip = ""
        elif ip:
            # If we're creating a DHCP IP address, that means it's actually
            # a DISCOVERED address, plus an empty DHCP address. DISCOVERED
            # addresses also aren't allocated to a particular user.
            if alloc_type == IPADDRESS_TYPE.DHCP:
                ipaddress = StaticIPAddress(
                    ip=ip,
                    alloc_type=IPADDRESS_TYPE.DISCOVERED,
                    subnet=subnet,
                    **kwargs,
                )
                ipaddress.save()
                ip = None
                alloc_type = IPADDRESS_TYPE.DHCP

        ipaddress = StaticIPAddress(
            ip=ip, alloc_type=alloc_type, user=user, subnet=subnet, **kwargs
        )
        ipaddress.save()
        if interface is not None:
            interface.ip_addresses.add(ipaddress)
            interface.save(force_update=True)
        if dnsresource is not None:
            dnsresource.ip_addresses.add(ipaddress)
            dnsresource.save(force_update=True)
        if hostname is not None:
            if not isinstance(hostname, (tuple, list)):
                hostname = [hostname]
            for name in hostname:
                if name.find(".") > 0:
                    name, domain = name.split(".", 1)
                    domain = Domain.objects.get(name=domain)
                else:
                    domain = None
                dnsrr, created = DNSResource.objects.get_or_create(
                    name=name, domain=domain
                )
                ipaddress.dnsresource_set.add(dnsrr)
        return reload_object(ipaddress)

    def make_email(self):
        return "%s@example.com" % self.make_string(10)

    def make_User(
        self,
        username=None,
        password="test",
        email=None,
        completed_intro=True,
        is_local=None,
        groups=(),
    ):
        if username is None:
            username = self.make_username()
        if email is None:
            email = self.make_email()
        user = User.objects.create_user(
            username=username, password=password, email=email
        )
        for group in groups:
            group.add(user)
        user.userprofile.completed_intro = completed_intro
        if is_local is not None:
            user.userprofile.is_local = is_local
        user.userprofile.save()
        return user

    def make_User_with_session(self, *args, **kwargs):
        user = self.make_User(*args, **kwargs)
        session = self._make_session(user)
        return user, session

    def _make_session(self, user):
        session = SessionStore()
        session["_auth_user_id"] = user.id
        session.save()
        return session

    def make_ResourcePool(self, name=None, description=None, nodes=None):
        if name is None:
            name = self.make_name("resourcepool")
        if description is None:
            description = self.make_string()
        pool = ResourcePool(name=name, description=description)
        pool.save()
        if nodes is not None:
            for node in nodes:
                node.pool = pool
                node.save()
        return pool

    def make_KeySource(self, protocol=None, auth_id=None, auto_update=False):
        if protocol is None:
            protocol = random.choice(
                [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
            )
        if auth_id is None:
            auth_id = factory.make_name("auth_id")
        keysource = KeySource(
            protocol=protocol, auth_id=auth_id, auto_update=auto_update
        )
        keysource.save()
        return keysource

    def make_SSHKey(self, user, key_string=None, keysource=None):
        if key_string is None:
            key_string = get_data("data/test_rsa0.pub")
        if keysource is None:
            keysource = self.make_KeySource(
                protocol=random.choice(
                    [KEYS_PROTOCOL_TYPE.LP, KEYS_PROTOCOL_TYPE.GH]
                )
            )
        key = SSHKey(key=key_string, user=user, keysource=keysource)
        key.save()
        return key

    def make_SSLKey(self, user, key_string=None):
        if key_string is None:
            key_string = get_data("data/test_x509_0.pem")
        key = SSLKey(key=key_string, user=user)
        key.save()
        return key

    def _maybe_make_Space(self, space):
        if isinstance(space, Space):
            return space
        make_random_space = False
        if space is RANDOM_OR_NONE:
            make_random_space = random.choice([True, False])
        if space is RANDOM:
            make_random_space = True
        if make_random_space:
            space = factory.make_Space()
        else:
            space = None
        return space

    def make_Space(self, name=None, description=""):
        space = Space(name=name, description=description)
        space.save()
        return space

    def make_Subnet(
        self,
        name=None,
        vlan=None,
        cidr=None,
        gateway_ip=RANDOM,
        dns_servers=None,
        host_bits=None,
        fabric=None,
        vid=None,
        dhcp_on=False,
        version=None,
        rdns_mode=RDNS_MODE.DEFAULT,
        allow_dns=True,
        allow_proxy=True,
        managed=True,
        space=RANDOM_OR_NONE,
        description="",
        disabled_boot_architectures=None,
        **kwargs,
    ):
        if name is None:
            name = factory.make_name("name")
        space = self._maybe_make_Space(space)
        if vlan is None:
            vlan = factory.make_VLAN(
                fabric=fabric, vid=vid, dhcp_on=dhcp_on, space=space
            )
        network = None
        if cidr is None:
            while True:
                network = factory.make_ip4_or_6_network(
                    version=version, host_bits=host_bits
                )
                # Loopback networks are special, so don't create them
                # randomly. If someone wants a loopback network, they
                # can pass in the cidr manually.
                if not network.is_loopback():
                    break
            cidr = str(network.cidr)
        if gateway_ip is RANDOM:
            network = IPNetwork(cidr) if network is None else network
            gateway_ip = inet_ntop(network.first + 1)
        if dns_servers is None:
            dns_servers = [
                self.make_ip_address() for _ in range(random.randint(1, 3))
            ]
        if disabled_boot_architectures is None and factory.pick_bool():
            disabled_boot_architectures = random.sample(
                [
                    boot_method.name
                    for _, boot_method in BootMethodRegistry
                    if boot_method.arch_octet or boot_method.path_prefix_http
                ],
                3,
            )
        elif disabled_boot_architectures is None:
            disabled_boot_architectures = []

        subnet = Subnet(
            name=name,
            vlan=vlan,
            cidr=cidr,
            gateway_ip=gateway_ip,
            dns_servers=dns_servers,
            rdns_mode=rdns_mode,
            allow_dns=allow_dns,
            allow_proxy=allow_proxy,
            managed=managed,
            description=description,
            disabled_boot_architectures=disabled_boot_architectures,
            **kwargs,
        )
        subnet.save()
        if subnet.vlan.space != space and space not in (undefined, None):
            subnet.vlan.space = space
            subnet.vlan.save()
        return subnet

    def make_StaticRoute(
        self, source=None, gateway_ip=None, destination=None, metric=None
    ):
        if source is None:
            source = factory.make_Subnet()
        version = source.get_ipnetwork().version
        if destination is None:
            destination = factory.make_Subnet(version=version)
        if gateway_ip is None:
            gateway_ip = factory.pick_ip_in_Subnet(source)
        if metric is None:
            metric = random.randint(0, 500)
        route = StaticRoute(
            source=source,
            destination=destination,
            gateway_ip=gateway_ip,
            metric=metric,
        )
        route.save()
        return route

    def pick_ip_in_Subnet(self, subnet, but_not=()):
        but_not = list(but_not)
        # Exclude all addresses currently in use
        for iprange in subnet.get_ipranges_in_use():
            but_not.append(iprange)
        return self.pick_ip_in_network(IPNetwork(subnet.cidr), but_not=but_not)

    def pick_ip_in_IPRange(self, ip_range, but_not=()):
        but_not = [IPAddress(but) for but in but_not]
        netaddr_range = ip_range.netaddr_iprange
        first = netaddr_range.first
        last = netaddr_range.last
        for _ in range(100):
            address = IPAddress(random.randint(first, last))
            if address not in but_not:
                return str(address)
        raise TooManyRandomRetries("Could not find available IP in IPRange")

    def make_Neighbour(
        self,
        ip=None,
        time=None,
        vid=0,
        count=None,
        interface=None,
        mac_address=None,
        updated=None,
        created=None,
    ):
        if ip is None:
            ip = factory.make_ipv4_address()
        if time is None:
            time = random.randint(0, 10000000)
        # Note that None is a valid value for vid, so we use 0 for the default.
        if vid == 0:
            vid = random.randint(1, 4094)
        if count is None:
            count = random.randint(1, 2000)
        if interface is None:
            rack = factory.make_RackController()
            interface = factory.make_Interface(node=rack)
        if mac_address is None:
            mac_address = factory.make_mac_address()
        neighbour = Neighbour(
            ip=ip,
            time=time,
            vid=vid,
            count=count,
            interface=interface,
            mac_address=mac_address,
        )
        neighbour.save(_updated=updated, _created=created)
        return neighbour

    def make_MDNS(
        self,
        hostname=None,
        ip=None,
        interface=None,
        updated=None,
        created=None,
    ):
        if hostname is None:
            hostname = factory.make_hostname()
        if interface is None:
            rack = factory.make_RackController()
            interface = factory.make_Interface(node=rack)
        mdns = MDNS(hostname=hostname, ip=ip, interface=interface)
        mdns.save(_updated=updated, _created=created)
        return mdns

    def make_RDNS(
        self,
        ip=None,
        hostname=None,
        observer=None,
        hostnames=None,
        updated=None,
        created=None,
    ):
        if observer is None:
            observer = RegionController.objects.first()
            if observer is None:
                observer = factory.make_RegionController()
        if hostname is None:
            hostname = factory.make_hostname()
        if hostnames is None:
            hostnames = [hostname]
        if ip is None:
            ip = factory.make_ip_address()
        rdns = RDNS(
            hostname=hostname, hostnames=hostnames, ip=ip, observer=observer
        )
        rdns.save(_updated=updated, _created=created)
        return rdns

    def make_Discovery(self, hostname=None, *args, **kwargs):
        # A Discovery is created indirectly, by creating each object that
        # must make up the discovery. Note that if an interface is specified,
        # it should reference a rack controller interface.
        neighbour = self.make_Neighbour(*args, **kwargs)
        interface = neighbour.interface
        if hostname is not None or random.choice([True, False]):
            if hostname != "":
                # Need a way to have a non-None hostname *and* specify that
                # no MDNS entry should be randomly created.
                self.make_MDNS(
                    hostname=hostname,
                    ip=neighbour.ip,
                    interface=interface,
                    updated=kwargs.get("updated", None),
                )
        # By using filter here, we guarantee that an object is returned.
        # If we search by the Neighbour ID we think we just created, there
        # might be no results, since the view might filter it.
        return get_one(
            Discovery.objects.filter(
                mac_address=neighbour.mac_address, ip=neighbour.ip
            )
        )

    def make_Fabric(self, name=None, class_type=None):
        fabric = Fabric(name=name, class_type=class_type)
        fabric.save()
        return fabric

    def make_Service(self, node, name=None):
        if name is None:
            name = self.make_name("name")
        service = Service(node=node, name=name)
        service.save()
        return service

    def _get_available_vid(self, fabric):
        """Return a free vid in the given Fabric."""
        taken_vids = set(fabric.vlan_set.all().values_list("vid", flat=True))
        for attempt in range(1000):
            vid = random.randint(1, 4094)
            if vid not in taken_vids:
                return vid
        raise maastesting.factory.TooManyRandomRetries(
            "Could not generate vid in fabric %s" % fabric
        )

    def make_VLAN(
        self,
        name=None,
        vid=None,
        fabric=None,
        dhcp_on=False,
        space=None,
        primary_rack=None,
        secondary_rack=None,
        relay_vlan=None,
        mtu=1500,
    ):
        assert vid != 0, "VID=0 VLANs are auto-created"
        if name is RANDOM:
            name = factory.make_name()
        if fabric is None:
            fabric = Fabric.objects.get_default_fabric()
        if vid is None:
            # Don't create the vid=0 VLAN, it's auto-created.
            vid = self._get_available_vid(fabric)
        space = self._maybe_make_Space(space)
        vlan = VLAN(
            name=name,
            vid=vid,
            fabric=fabric,
            dhcp_on=dhcp_on,
            space=space,
            primary_rack=primary_rack,
            secondary_rack=secondary_rack,
            relay_vlan=relay_vlan,
            mtu=mtu,
        )
        vlan.save()
        for rack in [primary_rack, secondary_rack]:
            if rack is None:
                continue
            if rack not in vlan.connected_rack_controllers():
                self.make_Interface(
                    INTERFACE_TYPE.PHYSICAL, node=rack, vlan=vlan
                )
        return vlan

    def make_Interface(
        self,
        iftype=INTERFACE_TYPE.PHYSICAL,
        node_config=None,
        node=None,
        mac_address=None,
        vlan=None,
        parents=None,
        name=None,
        cluster_interface=None,
        ip=None,
        subnet=None,
        enabled=True,
        fabric=None,
        tags=None,
        link_connected=True,
        interface_speed=None,
        link_speed=None,
        vendor=None,
        product=None,
        firmware_version=None,
        sriov_max_vf=0,
        params="",
        numa_node=None,
        neighbour_discovery_state=False,
        mdns_discovery_state=False,
    ):
        if numa_node is not None:
            node = numa_node.node
        # ensure node_config and node are either both set or both unset
        if node_config is None:
            if node is not None:
                node_config = node.current_config
            elif parents:
                node_config = parents[0].get_node().current_config
        if node_config is not None:
            node = node_config.node
        if iftype == INTERFACE_TYPE.PHYSICAL and node_config is None:
            # physical interfaces must have a node
            node_config = factory.make_NodeConfig()
            node = node_config.node

        if subnet is None and cluster_interface is not None:
            subnet = cluster_interface.subnet
        if subnet is not None and vlan is None:
            vlan = subnet.vlan
        if link_connected:
            if vlan is None:
                if fabric is not None:
                    if iftype == INTERFACE_TYPE.VLAN:
                        vlan = self.make_VLAN(fabric=fabric)
                    else:
                        vlan = fabric.get_default_vlan()
                else:
                    if iftype == INTERFACE_TYPE.VLAN and parents:
                        vlan = self.make_VLAN(fabric=parents[0].vlan.fabric)
                    elif parents and iftype in (
                        INTERFACE_TYPE.BOND,
                        INTERFACE_TYPE.BRIDGE,
                    ):
                        vlan = parents[0].vlan
                    else:
                        fabric = self.make_Fabric()
                        vlan = fabric.get_default_vlan()
        if name is None:
            if iftype in (INTERFACE_TYPE.PHYSICAL, INTERFACE_TYPE.UNKNOWN):
                name = self.make_name("eth")
            elif iftype == INTERFACE_TYPE.ALIAS:
                name = self.make_name("eth", sep=":")
            elif iftype == INTERFACE_TYPE.BOND:
                name = self.make_name("bond")
            elif iftype == INTERFACE_TYPE.BRIDGE:
                name = self.make_name("br")
            elif iftype == INTERFACE_TYPE.UNKNOWN:
                name = self.make_name("eth")
            elif iftype == INTERFACE_TYPE.VLAN:
                # Need to calculate this later based on the VID.
                if vlan is not None and vlan.vid:
                    if parents:
                        name = f"{parents[0].name}.{vlan.vid}"
                    else:
                        name = f"{self.make_name('eth')}.{vlan.vid}"
                else:
                    name = self.make_name("vlan")
        if None not in (parents, name) and iftype == INTERFACE_TYPE.VLAN:
            name = "%s.%d" % (parents[0].name, vlan.vid)
        if mac_address is None and iftype in [
            INTERFACE_TYPE.PHYSICAL,
            INTERFACE_TYPE.BOND,
            INTERFACE_TYPE.BRIDGE,
            INTERFACE_TYPE.UNKNOWN,
        ]:
            mac_address = self.make_mac_address()
        if tags is None:
            tags = [self.make_name("tag") for _ in range(3)]
        link_speeds = [10, 100, 1000, 10000, 20000, 40000, 50000, 100000]
        if interface_speed is None:
            interface_speed = random.choice(link_speeds)
        if link_speed is None:
            if not link_connected:
                link_speed = 0
            else:
                link_speed = random.choice(
                    [
                        speed
                        for speed in link_speeds
                        if speed <= interface_speed
                    ]
                )
        if vendor is None:
            vendor = factory.make_name("vendor")
        if product is None:
            product = factory.make_name("product")
        if (
            iftype == INTERFACE_TYPE.PHYSICAL
            and numa_node is None
            and node.is_machine
        ):
            numa_node = node_config.node.default_numanode
        interface = Interface(
            node_config=node_config,
            mac_address=mac_address,
            type=iftype,
            name=name,
            vlan=vlan,
            enabled=enabled,
            tags=tags,
            link_connected=link_connected,
            interface_speed=interface_speed,
            link_speed=link_speed,
            vendor=vendor,
            product=product,
            firmware_version=firmware_version,
            sriov_max_vf=sriov_max_vf,
            params=params,
            numa_node=numa_node,
            neighbour_discovery_state=neighbour_discovery_state,
            mdns_discovery_state=mdns_discovery_state,
        )
        interface.save()
        if subnet is None and ip is not None:
            subnet = Subnet.objects.get_best_subnet_for_ip(ip)
        if subnet is not None:
            sip = StaticIPAddress.objects.create(
                ip=ip,
                alloc_type=(
                    IPADDRESS_TYPE.DHCP
                    if ip is None
                    else IPADDRESS_TYPE.STICKY
                ),
                subnet=subnet,
            )
            interface.ip_addresses.add(sip)
        if parents:
            for parent in parents:
                InterfaceRelationship(child=interface, parent=parent).save()
        interface.save(force_update=True)
        if interface.type == INTERFACE_TYPE.PHYSICAL:
            self.make_NodeDevice(
                bus=NODE_DEVICE_BUS.PCIE,
                hardware_type=HARDWARE_TYPE.NETWORK,
                node=node,
                numa_node=numa_node,
                physical_interface=interface,
            )
        return reload_object(interface)

    def make_IPRange(
        self,
        subnet=None,
        start_ip=None,
        end_ip=None,
        comment=None,
        user=None,
        alloc_type=None,
    ):
        if alloc_type is None:
            alloc_type = (
                IPRANGE_TYPE.RESERVED if user else IPRANGE_TYPE.DYNAMIC
            )

        if subnet is None and start_ip is None and end_ip is None:
            subnet = self.make_ipv4_Subnet_with_IPRanges()
            iprange = subnet.get_dynamic_ranges().first()
            iprange.comment = comment
            iprange.user = user
            iprange.type = alloc_type
            iprange.save()
            return iprange

        # If any of these values are provided, they must all be provided.
        assert subnet is not None
        assert start_ip is not None
        assert end_ip is not None
        iprange = IPRange(
            subnet=subnet,
            start_ip=start_ip,
            end_ip=end_ip,
            type=alloc_type,
            comment=comment,
            user=user,
        )
        iprange.save()
        return iprange

    def make_ipv4_Subnet_with_IPRanges(
        self,
        cidr=None,
        unmanaged=False,
        with_dynamic_range=True,
        with_static_range=True,
        dns_servers=None,
        with_router=True,
        **kwargs,
    ):
        if cidr is not None:
            network = IPNetwork(cidr)
            slash = network.prefixlen
        else:
            slash = random.choice(
                [16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28]
            )
            network = factory.make_ipv4_network(slash=slash)
        host_bits = 32 - slash
        # Use at most 25% of the subnet per range type.
        range_size = 2 ** (host_bits - 2)
        if with_router:
            router_address = IPAddress(network.first + 1)
        else:
            router_address = ""
        if dns_servers is None:
            dns_servers = random.choice(
                [
                    [],
                    ["8.8.8.8", "8.8.4.4"],
                    [str(IPAddress(network.last - 1))],
                ]
            )
        subnet = self.make_Subnet(
            cidr=str(network),
            gateway_ip=str(router_address),
            dns_servers=dns_servers,
            **kwargs,
        )
        # Create a "dynamic range" for this Subnet.
        if with_dynamic_range:
            if unmanaged:
                subnet.vlan.dhcp_on = False
                subnet.vlan.save()
            else:
                subnet.vlan.dhcp_on = True
                subnet.vlan.save()
            self.make_IPRange(
                subnet,
                alloc_type=IPRANGE_TYPE.DYNAMIC,
                start_ip=str(IPAddress(network.first + 2)),
                end_ip=str(IPAddress(network.first + range_size + 2)),
            )
        # Create a "static range" for this Subnet.
        if not with_static_range:
            self.make_IPRange(
                subnet,
                alloc_type=IPRANGE_TYPE.RESERVED,
                start_ip=str(IPAddress(network.last - range_size - 2)),
                end_ip=str(IPAddress(network.last - 2)),
            )
        return reload_object(subnet)

    def make_managed_Subnet_for(self, cidr, dhcp=True):
        network = IPNetwork(cidr)
        router_address = IPAddress(network.first + 1)
        dns_servers = random.choice(
            [[], ["8.8.8.8", "8.8.4.4"], [str(IPAddress(network.last - 1))]]
        )
        subnet = self.make_Subnet(
            cidr=str(network),
            gateway_ip=str(router_address),
            dns_servers=dns_servers,
        )
        if dhcp:
            subnet.vlan.dhcp_on = True
            subnet.vlan.save()
        else:
            subnet.vlan.dhcp_on = False
            subnet.vlan.save()
        return subnet

    def make_managed_Subnet(self, *, ipv6=None, dhcp=True):
        if ipv6 is None:
            ipv6 = self.pick_bool()
        if ipv6:
            slash = random.randint(48, 80)  # Not too small.
            cidr = factory.make_ipv6_network(slash=slash)
        else:
            slash = random.randint(16, 20)  # Not too small.
            cidr = factory.make_ipv4_network(slash=slash)
        return self.make_managed_Subnet_for(cidr, dhcp=dhcp)

    def make_Tag(
        self,
        name=None,
        definition=None,
        comment="",
        kernel_opts="",
        created=None,
        updated=None,
        populate=True,
    ):
        if name is None:
            name = self.make_name("tag")
        if definition is None:
            # Is there a 'node' in this xml?
            definition = "//node"
        tag = Tag(
            name=name,
            definition=definition,
            comment=comment,
            kernel_opts=kernel_opts,
        )
        # Save without populating nodes.
        tag.save(populate=False)
        # Update the 'updated'/'created' fields with a call to 'update'
        # preventing a call to save() from overriding the values.
        if updated is not None:
            Tag.objects.filter(id=tag.id).update(updated=updated)
        if created is not None:
            Tag.objects.filter(id=tag.id).update(created=created)
        # Reload if we've changed the underlying record.
        if updated is not None or created is not None:
            tag = reload_object(tag)
        # Populate nodes for this tag now that it's fully configured, if
        # requested. This avoids dealing with the post-commit hook stuff.
        if populate:
            tag._populate_nodes_now()
        return tag

    def make_user_with_keys(
        self, n_keys=2, user=None, keysource=None, **kwargs
    ):
        """Create a user with n `SSHKey`.  If user is not None, use this user
        instead of creating one.  If keysource is not None, use this keysource
        instaed of creating one.

        Additional keyword arguments are passed to `make_user()`.
        """
        if n_keys > MAX_PUBLIC_KEYS:
            raise RuntimeError(
                "Cannot create more than %d public keys.  If you need more: "
                "add more keys in src/maasserver/tests/data/."
                % MAX_PUBLIC_KEYS
            )
        if user is None:
            user = self.make_User(**kwargs)
        if keysource is None:
            keysource = self.make_KeySource()
        keys = []
        for i in range(n_keys):
            key_string = get_data("data/test_rsa%d.pub" % i)
            key = SSHKey(user=user, key=key_string, keysource=keysource)
            key.save()
            keys.append(key)
        return user, keys

    def make_user_with_ssl_keys(self, n_keys=2, user=None, **kwargs):
        """Create a user with n `SSLKey`.

        :param n_keys: Number of keys to add to user.
        :param user: User to add keys to. If user is None, then user is made
            with make_user. Additional keyword arguments are passed to
            `make_user()`.
        """
        if n_keys > MAX_PUBLIC_KEYS:
            raise RuntimeError(
                "Cannot create more than %d public keys.  If you need more: "
                "add more keys in src/maasserver/tests/data/."
                % MAX_PUBLIC_KEYS
            )
        if user is None:
            user = self.make_User(**kwargs)
        keys = []
        for i in range(n_keys):
            key_string = get_data("data/test_x509_%d.pem" % i)
            key = SSLKey(user=user, key=key_string)
            key.save()
            keys.append(key)
        return user, keys

    def make_admin(
        self, username=None, password="test", email=None, completed_intro=True
    ):
        if username is None:
            username = self.make_username()
        if email is None:
            email = self.make_email()
        user = User.objects.create_superuser(
            username, password=password, email=email
        )
        user.userprofile.completed_intro = completed_intro
        user.userprofile.save()
        return user

    def make_admin_with_session(self, *args, **kwargs):
        admin = self.make_admin(*args, **kwargs)
        session = self._make_session(admin)
        return admin, session

    def make_FileStorage(self, filename=None, content=None, owner=None):
        fake_file = self.make_file_upload(filename, content)
        return FileStorage.objects.save_file(fake_file.name, fake_file, owner)

    def make_oauth_header(self, missing_param=None, **kwargs):
        """Fake an OAuth authorization header.

        This will use arbitrary values.  Pass as keyword arguments any
        header items that you wish to override.
        :param missing_param: Optional parameter name.  This parameter will
            be omitted from the OAuth header.  This is used to create bogus
            OAuth headers to make sure the code deals properly with them.
        """
        items = {
            "realm": self.make_string(),
            "oauth_nonce": random.randint(0, 99999),
            "oauth_timestamp": time.time(),
            "oauth_consumer_key": self.make_string(18),
            "oauth_signature_method": "PLAINTEXT",
            "oauth_version": "1.0",
            "oauth_token": self.make_string(18),
            "oauth_signature": "%%26%s" % self.make_string(32),
        }
        items.update(kwargs)
        if missing_param is not None:
            del items[missing_param]
        return "OAuth " + ", ".join(
            [f'{key}="{value}"' for key, value in items.items()]
        )

    def make_Zone(
        self, name=None, description=None, nodes=None, sortable_name=False
    ):
        """Create a physical `Zone`.

        :param sortable_name: If `True`, use a that will sort consistently
            between different collation orders.  Use this when testing sorting
            by name, where the database and the python code may have different
            ideas about collation orders, especially when it comes to case
            differences.
        """
        if name is None:
            name = self.make_name("zone")
        if sortable_name:
            name = name.lower()
        if description is None:
            description = self.make_string()
        zone = Zone(name=name, description=description)
        zone.save()
        if nodes is not None:
            zone.node_set.add(*nodes)
        return zone

    make_zone = make_Zone

    def make_BootSource(
        self, url=None, keyring_filename=None, keyring_data=None
    ):
        """Create a new `BootSource`."""
        if url is None:
            url = "http://%s.com/" % self.make_name("source-url")
        # Only set _one_ of keyring_filename and keyring_data.
        if keyring_filename is None and keyring_data is None:
            keyring_filename = self.make_name("keyring")
        boot_source = BootSource(
            url=url,
            keyring_filename=(
                "" if keyring_filename is None else keyring_filename
            ),
            keyring_data=(b"" if keyring_data is None else keyring_data),
        )
        boot_source.save()
        return boot_source

    def make_BootSourceCache(
        self,
        boot_source=None,
        os=None,
        arch=None,
        subarch=None,
        release=None,
        label=None,
        release_codename=None,
        release_title=None,
        support_eol=None,
        kflavor=None,
        bootloader_type=None,
    ):
        """Create a new `BootSourceCache`."""
        if boot_source is None:
            boot_source = self.make_BootSource()
        if os is None:
            os = factory.make_name("os")
        if arch is None:
            arch = factory.make_name("arch")
        if subarch is None:
            subarch = factory.make_name("subarch")
        if release is None:
            release = factory.make_name("release")
        if label is None:
            label = factory.make_name("label")
        return BootSourceCache.objects.create(
            boot_source=boot_source,
            os=os,
            arch=arch,
            subarch=subarch,
            release=release,
            label=label,
            release_codename=release_codename,
            release_title=release_title,
            support_eol=support_eol,
            kflavor=kflavor,
            bootloader_type=bootloader_type,
        )

    def make_many_BootSourceCaches(self, number, **kwargs):
        caches = list()
        for _ in range(number):
            caches.append(self.make_BootSourceCache(**kwargs))
        return caches

    def make_BootSourceSelection(
        self,
        boot_source=None,
        os=None,
        release=None,
        arches=None,
        subarches=None,
        labels=None,
    ):
        """Create a `BootSourceSelection`."""
        if boot_source is None:
            boot_source = self.make_BootSource()
        if os is None:
            os = self.make_name("os")
        if release is None:
            release = self.make_name("release")
        if arches is None:
            arch_count = random.randint(1, 10)
            arches = [self.make_name("arch") for _ in range(arch_count)]
        if subarches is None:
            subarch_count = random.randint(1, 10)
            subarches = [
                self.make_name("subarch") for _ in range(subarch_count)
            ]
        if labels is None:
            label_count = random.randint(1, 10)
            labels = [self.make_name("label") for _ in range(label_count)]
        boot_source_selection = BootSourceSelection(
            boot_source=boot_source,
            os=os,
            release=release,
            arches=arches,
            subarches=subarches,
            labels=labels,
        )
        boot_source_selection.save()
        return boot_source_selection

    def make_LicenseKey(
        self, osystem=None, distro_series=None, license_key=None
    ):
        if osystem is None:
            osystem = factory.make_name("osystem")
        if distro_series is None:
            distro_series = factory.make_name("distro_series")
        if license_key is None:
            license_key = factory.make_name("key")
        return LicenseKey.objects.create(
            osystem=osystem,
            distro_series=distro_series,
            license_key=license_key,
        )

    def make_EventType(self, name=None, level=None, description=None):
        if name is None:
            name = self.make_name("name", size=20)
        if description is None:
            description = factory.make_name("description")
        if level is None:
            level = random.choice(
                [logging.ERROR, logging.WARNING, logging.INFO, logging.DEBUG]
            )
        return EventType.objects.create(
            name=name, description=description, level=level
        )

    def make_Event(
        self,
        type=None,
        node=None,
        user=None,
        ip_address=None,
        endpoint=None,
        user_agent=None,
        action=None,
        description=None,
    ):
        if type is None:
            type = self.make_EventType()
        if node is None:
            node = self.make_Node()
            node_hostname = ""
        else:
            node_hostname = node.hostname
        if user is None:
            user = self.make_User()
        user_id = user.id
        username = user.username
        if ip_address is None:
            ip_address = factory.make_ipv4_address()
        if endpoint is None:
            endpoint = self.pick_choice(ENDPOINT_CHOICES)
        if user_agent is None:
            user_agent = factory.make_name("user_agent")
        if action is None:
            action = self.make_name("action")
        if description is None:
            description = self.make_name("desc")
        return Event.objects.create(
            type=type,
            node=node,
            node_system_id=node.system_id,
            node_hostname=node_hostname,
            user_id=user_id,
            username=username,
            ip_address=ip_address,
            endpoint=endpoint,
            user_agent=user_agent,
            action=action,
            description=description,
        )

    def make_boot_file(
        self, content: bytes | None = None, size: int | None = None
    ) -> LocalBootResourceFile:
        """Create a boot resource file with content
        the file will be named after its SHA256 hash

        :param content: Data to store in large file object.
        :param size: Size of `content`. If `content` is None
            then it will be a random string of this size.

        returns LocalBootResourceFile
        """
        if content is None:
            size = size or 512
            content = factory.make_bytes(size=size)
        if size is None:
            size = len(content)
        sha256 = hashlib.sha256()
        sha256.update(content)
        filehash = sha256.hexdigest()

        lf = LocalBootResourceFile(sha256=filehash, total_size=size)
        with lf.store() as m:
            m.write(content)
        return lf

    def make_base_image_name(self, osystem=None, release=None):
        if osystem is None:
            osystem = "ubuntu"
        if release is None:
            release = OperatingSystemRegistry[osystem].get_default_release()
        return f"{osystem}/{release}"

    def make_BootResource(
        self,
        rtype=None,
        name=None,
        architecture=None,
        extra=None,
        kflavor=None,
        bootloader_type=None,
        rolling=False,
        base_image="",
        platform="generic",
        supported_platforms="generic",
    ) -> BootResource:
        if rtype is None:
            if base_image:
                rtype = BOOT_RESOURCE_TYPE.UPLOADED
            else:
                rtype = self.pick_enum(BOOT_RESOURCE_TYPE)
        if name is None:
            if rtype == BOOT_RESOURCE_TYPE.UPLOADED:
                name = self.make_name("name")
            else:
                os = self.make_name("os")
                series = self.make_name("series")
                name = f"{os}/{series}"
        subarch = None
        if architecture is None:
            arch = self.make_name("arch")
            subarch = self.make_name("subarch")
            architecture = f"{arch}/{subarch}"
        if extra is None:
            extra = {
                self.make_name("key"): self.make_name("value")
                for _ in range(3)
            }

        if "platform" in extra and platform is None:
            del extra["platform"]
        elif platform is not None:
            extra.setdefault("platform", platform)

        if "supported_platforms" in extra and supported_platforms is None:
            del extra["supported_platforms"]
        elif supported_platforms is not None:
            extra.setdefault("supported_platforms", supported_platforms)

        if subarch and "supported_platforms" in extra:
            extra["supported_platforms"] += "," + subarch

        result = BootResource.objects.create(
            rtype=rtype,
            name=name,
            architecture=architecture,
            kflavor=kflavor,
            bootloader_type=bootloader_type,
            extra=extra,
            rolling=rolling,
            base_image=base_image,
        )
        return result

    def make_BootResourceSet(
        self,
        resource: BootResource,
        version: str | None = None,
        label: str | None = None,
    ) -> BootResourceSet:
        if version is None:
            version = self.make_name("version")
        if label is None:
            label = self.make_name("label")
        return BootResourceSet.objects.create(
            resource=resource, version=version, label=label
        )

    def make_BootResourceFile(
        self,
        resource_set: BootResourceSet,
        filename: str | None = None,
        filetype: str | None = None,
        sha256: str | None = None,
        extra: dict | None = None,
        size: int = 0,
        largefile: LargeFile | None = None,
        synced: Iterable[tuple[RegionController, int]] | None = None,
    ) -> BootResourceFile:
        if sha256 is None:
            sha256 = (
                largefile.sha256 if largefile else factory.make_hex_string(64)
            )
        if filename is None:
            filename = self.make_name("name")
        if filetype is None:
            filetype = self.pick_enum(BOOT_RESOURCE_FILE_TYPE)
        if extra is None:
            extra = {
                self.make_name("key"): self.make_name("value")
                for _ in range(3)
            }
        rfile = BootResourceFile.objects.create(
            resource_set=resource_set,
            filename=filename,
            filetype=filetype,
            extra=extra,
            sha256=sha256,
            size=size,
            largefile=largefile,
        )

        if synced:
            for st in synced:
                sync_size = rfile.size if st[1] < 0 else st[1]
                rfile.bootresourcefilesync_set.create(
                    region=st[0], size=sync_size
                )

        return rfile

    def make_boot_resource_file_with_content(
        self,
        resource_set: BootResourceSet,
        filename: str | None = None,
        filetype: str | None = None,
        extra: str | None = None,
        content: bytes | None = None,
        size: int | None = None,
        synced: Iterable[tuple[RegionController, int]] | None = None,
    ) -> BootResourceFile:
        lfile = self.make_boot_file(content=content, size=size)
        return self.make_BootResourceFile(
            resource_set,
            filename=filename,
            filetype=filetype,
            sha256=lfile.sha256,
            size=lfile.size,
            extra=extra,
            synced=synced,
        )

    def make_usable_boot_resource(
        self,
        rtype=None,
        name=None,
        architecture=None,
        extra=None,
        version=None,
        label=None,
        kflavor=None,
        size=None,
        bootloader_type=None,
        rolling=False,
        filename=None,
        image_filetype=BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
        base_image="",
        platform="generic",
        supported_platforms="generic",
    ):
        resource = self.make_BootResource(
            rtype=rtype,
            name=name,
            architecture=architecture,
            extra=extra,
            kflavor=kflavor,
            bootloader_type=bootloader_type,
            rolling=rolling,
            base_image=base_image,
            platform=platform,
            supported_platforms=supported_platforms,
        )
        resource_set = self.make_BootResourceSet(
            resource,
            version=version,
            label=label,
        )
        filetypes = {
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
        }
        filetypes.add(image_filetype)
        for filetype in filetypes:
            # We set the filename to the same value as filetype, as in most
            # cases this will always be true. The simplestreams content from
            # maas.io, is formatted this way.
            self.make_boot_resource_file_with_content(
                resource_set,
                filename=filename,
                filetype=filetype,
                size=None,
                extra=extra,
                synced=[(r, -1) for r in RegionController.objects.all()],
            )
        return resource

    def make_custom_boot_resource(
        self,
        name=None,
        architecture=None,
        extra=None,
        version=None,
        label=None,
        filename=None,
        filetype=None,
        base_image="",
        platform=None,
        supported_platforms=None,
    ):
        resource = self.make_BootResource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name,
            architecture=architecture,
            extra=extra,
            base_image=base_image,
            platform=platform,
            supported_platforms=supported_platforms,
        )
        resource_set = self.make_BootResourceSet(
            resource,
            version=version,
            label=label,
        )
        if filetype is None:
            filetype = random.choice(
                [
                    BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
                    BOOT_RESOURCE_FILE_TYPE.ROOT_DDTGZ,
                    BOOT_RESOURCE_FILE_TYPE.ROOT_DDRAW,
                ]
            )
        self.make_boot_resource_file_with_content(
            resource_set,
            filename=filename,
            filetype=filetype,
            size=None,
            extra=extra,
            synced=[(r, -1) for r in RegionController.objects.all()],
        )
        return resource

    def make_incomplete_boot_resource(
        self,
        rtype=None,
        name=None,
        architecture=None,
        extra=None,
        version=None,
        label=None,
        kflavor=None,
        size=None,
        bootloader_type=None,
        filename=None,
        platform=None,
        supported_platforms=None,
        resource_synced: list[RegionController] | None = None,
    ):
        resource = self.make_BootResource(
            rtype=rtype,
            name=name,
            architecture=architecture,
            extra=extra,
            kflavor=kflavor,
            bootloader_type=bootloader_type,
            platform=platform,
            supported_platforms=supported_platforms,
        )
        resource_set = self.make_BootResourceSet(
            resource,
            version=version,
            label=label,
        )
        filetypes = {
            BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL,
            BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD,
        }
        filetypes.add(
            random.choice(
                [
                    BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE,
                    BOOT_RESOURCE_FILE_TYPE.ROOT_IMAGE,
                ]
            )
        )
        filetypes.add(random.choice(XINSTALL_TYPES))
        for filetype in filetypes:
            # Create a half completed file.
            size = 512
            content = factory.make_bytes(256)
            sync_status = (
                [(r, -1) for r in resource_synced] if resource_synced else None
            )
            self.make_boot_resource_file_with_content(
                resource_set,
                filename=filename,
                filetype=filetype,
                size=size,
                content=content,
                synced=sync_status,
            )

        return resource

    def make_default_ubuntu_release_bootable(self, arch=None, extra=None):
        if arch is None:
            arch = self.make_name("arch")
        default_osystem = Config.objects.get_config(
            name="commissioning_osystem"
        )
        default_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        default_name = f"{default_osystem}/{default_series}"
        release = get_release_from_distro_info(default_series)
        architecture = "{}/hwe-{}".format(arch, release["version"].split()[0])
        try:
            return BootResource.objects.get(
                name=default_name,
                architecture=architecture,
                rtype=BOOT_RESOURCE_TYPE.SYNCED,
            )
        except BootResource.DoesNotExist:
            with transaction.atomic():
                return self.make_usable_boot_resource(
                    name=default_name,
                    architecture=architecture,
                    kflavor="generic",
                    rtype=BOOT_RESOURCE_TYPE.SYNCED,
                    extra=extra,
                )

    def make_BlockDevice(
        self,
        node_config=None,
        node=None,
        name=None,
        id_path=None,
        size=None,
        block_size=None,
        tags=None,
    ):
        if node_config is None:
            if node is None:
                node_config = factory.make_NodeConfig()
            else:
                node_config = node.current_config
        if name is None:
            name = self.make_name("name")
        if id_path is None:
            id_path = "/dev/disk/by-id/id_%s" % name
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if size is None:
            size = round_size_to_nearest_block(
                random.randint(
                    MIN_BLOCK_DEVICE_SIZE * 4, MIN_BLOCK_DEVICE_SIZE * 1024
                ),
                block_size,
            )
        if tags is None:
            tags = [self.make_name("tag") for _ in range(3)]
        return BlockDevice.objects.create(
            node_config=node_config,
            name=name,
            size=size,
            block_size=block_size,
            tags=tags,
        )

    def make_PhysicalBlockDevice(
        self,
        node_config=None,
        node=None,
        name=None,
        size=None,
        block_size=None,
        tags=None,
        model=None,
        serial=None,
        id_path=None,
        formatted_root=False,
        firmware_version=None,
        numa_node=None,
        pcie=False,
        bootable=False,
    ):
        if node is None:
            if node_config is not None:
                node = node_config.node
            elif numa_node is not None:
                node = numa_node.node
            else:
                node = factory.make_Node()
        if numa_node is None:
            numa_node = node.default_numanode
        if node_config is None:
            node_config = node.current_config
        if name is None:
            name = self.make_name("name")
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if size is None:
            # We need space for MakePartition to choose "largest" _3_ times,
            # because of TestManagersFilterByNode.test__bcache_on_partitions
            # in maasserver/models/tests/test_filesystemgroup.py.
            size = round_size_to_nearest_block(
                random.randint(
                    max(MIN_BLOCK_DEVICE_SIZE, MIN_PARTITION_SIZE) * 64,
                    MIN_BLOCK_DEVICE_SIZE * 1024,
                ),
                block_size,
            )
            if bootable and size < MIN_BOOT_PARTITION_SIZE:
                size = MIN_BOOT_PARTITION_SIZE
        if tags is None:
            tags = [self.make_name("tag") for _ in range(3)]
        if id_path is None:
            if model is None:
                model = self.make_name("model")
            if serial is None:
                serial = self.make_name("serial")
        else:
            model = ""
            serial = ""
        if firmware_version is None:
            firmware_version = factory.make_name("firmware_version")
        block_device = PhysicalBlockDevice.objects.create(
            node_config=node_config,
            name=name,
            size=size,
            block_size=block_size,
            tags=tags,
            model=model,
            serial=serial,
            id_path=id_path,
            firmware_version=firmware_version,
            numa_node=numa_node,
        )
        # Only NVMe drives have a NodeDevice associated with them since
        # they are PCIE devices.
        if pcie:
            self.make_NodeDevice(
                bus=NODE_DEVICE_BUS.PCIE,
                hardware_type=HARDWARE_TYPE.STORAGE,
                node=node_config.node,
                numa_node=numa_node,
                physical_blockdevice=block_device,
            )
        if formatted_root:
            partition = self.make_Partition(
                partition_table=(
                    self.make_PartitionTable(block_device=block_device)
                )
            )
            self.make_Filesystem(mount_point="/", partition=partition)
        return block_device

    def make_PartitionTable(
        self,
        table_type=PARTITION_TABLE_TYPE.GPT,
        block_device=None,
        node=None,
        block_device_size=None,
        bootable=False,
    ):
        if block_device is None:
            if node is None:
                if table_type == PARTITION_TABLE_TYPE.GPT:
                    node = factory.make_Node(bios_boot_method="uefi")
                else:
                    node = factory.make_Node()
            block_device = self.make_PhysicalBlockDevice(
                node_config=node.current_config,
                size=block_device_size,
                bootable=bootable,
            )
        return PartitionTable.objects.create(
            table_type=table_type, block_device=block_device
        )

    def make_Partition(
        self,
        partition_table=None,
        uuid=None,
        size=None,
        bootable=None,
        node=None,
        block_device_size=None,
        tags=None,
    ):
        if partition_table is None:
            partition_table = self.make_PartitionTable(
                node=node,
                block_device_size=block_device_size,
                bootable=bootable,
            )
        if size is None:
            available_size = partition_table.get_available_size() // 2
            if available_size < MIN_PARTITION_SIZE:
                raise ValueError(
                    "Cannot make another partition on partition_table not "
                    "enough free space."
                )
            size = random.randint(MIN_PARTITION_SIZE, available_size)
        if bootable is None:
            bootable = random.choice([True, False])
        if tags is None:
            tags = [self.make_name("tag") for _ in range(3)]
        return Partition.objects.create(
            partition_table=partition_table,
            uuid=uuid,
            size=size,
            bootable=bootable,
            tags=tags,
        )

    def pick_filesystem_type(self, but_not=()):
        """Pick a filesystem that requires block storage and a mount point."""
        # XXX: Temporarily exclude swap, ramfs, and tmpfs from the random
        # choice. Swap doesn't use a mount point, and ramfs/tmpfs don't use
        # storage, and this can surprise some tests. This is obviously not a
        # tenable position longer term.
        but_not = {
            FILESYSTEM_TYPE.SWAP,
            FILESYSTEM_TYPE.RAMFS,
            FILESYSTEM_TYPE.TMPFS,
        }.union(but_not)
        return factory.pick_choice(
            FILESYSTEM_FORMAT_TYPE_CHOICES, but_not=but_not
        )

    def pick_any_filesystem_type(self, but_not=()):
        """Pick any filesystem type, including swap, ramfs, or tmpfs."""
        return factory.pick_choice(
            FILESYSTEM_FORMAT_TYPE_CHOICES, but_not=but_not
        )

    def make_Filesystem(
        self,
        uuid=None,
        fstype=None,
        partition=None,
        block_device=None,
        node_config=None,
        filesystem_group=None,
        label=None,
        create_params=None,
        mount_point=None,
        mount_options=undefined,
        block_device_size=None,
        acquired=False,
    ):
        if fstype is None:
            if node_config is None:
                # Pick a filesystem that requires storage and a mount point.
                fstype = self.pick_filesystem_type()
            else:
                # Pick a filesystem that does not require storage, like tmpfs.
                fstype = self.pick_any_filesystem_type(
                    but_not=Filesystem.TYPES_REQUIRING_STORAGE
                )
        if fstype in Filesystem.TYPES_REQUIRING_STORAGE:
            if partition is None and block_device is None:
                if self.pick_bool():
                    partition = self.make_Partition()
                else:
                    block_device = self.make_PhysicalBlockDevice(
                        size=block_device_size
                    )
        else:
            if mount_point is None:
                mount_point = factory.make_absolute_path()
        if mount_options is undefined:
            mount_options = self.make_name("mount-options")

        node = None
        if partition is not None:
            node = partition.get_node()
        elif block_device is not None:
            node = block_device.get_node()
        if node_config is None:
            if node is None:
                node_config = self.make_NodeConfig()
            else:
                node_config = node.current_config
        return Filesystem.objects.create(
            uuid=uuid,
            fstype=fstype,
            partition=partition,
            block_device=block_device,
            node_config=node_config,
            filesystem_group=filesystem_group,
            label=label,
            create_params=create_params,
            mount_point=mount_point,
            mount_options=mount_options,
            acquired=acquired,
        )

    def make_CacheSet(self, block_device=None, partition=None, node=None):
        if node is None:
            node = self.make_Node()
        if partition is None and block_device is None:
            if self.pick_bool():
                partition = self.make_Partition(node=node)
            else:
                block_device = self.make_PhysicalBlockDevice(node=node)
        if block_device is not None:
            return CacheSet.objects.get_or_create_cache_set_for_block_device(
                block_device
            )
        else:
            return CacheSet.objects.get_or_create_cache_set_for_partition(
                partition
            )

    def make_FilesystemGroup(
        self,
        uuid=None,
        group_type=None,
        name=None,
        create_params=None,
        filesystems=None,
        node=None,
        block_device_size=None,
        cache_mode=None,
        num_lvm_devices=4,
        cache_set=None,
    ):
        if group_type is None:
            group_type = self.pick_enum(FILESYSTEM_GROUP_TYPE)
        if group_type == FILESYSTEM_GROUP_TYPE.BCACHE:
            if cache_mode is None:
                cache_mode = self.pick_enum(CACHE_MODE_TYPE)
            if cache_set is None:
                cache_set = self.make_CacheSet(node=node)
        group = FilesystemGroup(
            uuid=uuid,
            group_type=group_type,
            name=name,
            cache_mode=cache_mode,
            create_params=create_params,
            cache_set=cache_set,
        )
        group.save()
        if filesystems is None:
            if node is None:
                node = self.make_Node()
            node_config = node.current_config
            if not node.physicalblockdevice_set.exists():
                # Add the boot disk and leave it as is.
                self.make_PhysicalBlockDevice(
                    node_config=node_config, bootable=True
                )
            if group_type == FILESYSTEM_GROUP_TYPE.LVM_VG:
                for _ in range(num_lvm_devices):
                    block_device = self.make_PhysicalBlockDevice(
                        node_config=node_config, size=block_device_size
                    )
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.LVM_PV,
                        block_device=block_device,
                    )
                    group.filesystems.add(filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_0:
                for _ in range(2):
                    block_device = self.make_PhysicalBlockDevice(
                        node_config=node_config
                    )
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID, block_device=block_device
                    )
                    group.filesystems.add(filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_1:
                for _ in range(2):
                    block_device = self.make_PhysicalBlockDevice(
                        node_config=node_config
                    )
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID, block_device=block_device
                    )
                    group.filesystems.add(filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_5:
                for _ in range(3):
                    block_device = self.make_PhysicalBlockDevice(
                        node_config=node_config
                    )
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID, block_device=block_device
                    )
                    group.filesystems.add(filesystem)
                spare_block_device = self.make_PhysicalBlockDevice(
                    node_config=node_config
                )
                spare_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=spare_block_device,
                )
                group.filesystems.add(spare_filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_6:
                for _ in range(4):
                    block_device = self.make_PhysicalBlockDevice(
                        node_config=node_config
                    )
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID, block_device=block_device
                    )
                    group.filesystems.add(filesystem)
                spare_block_device = self.make_PhysicalBlockDevice(
                    node_config=node_config
                )
                spare_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=spare_block_device,
                )
                group.filesystems.add(spare_filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.RAID_10:
                for _ in range(4):
                    block_device = self.make_PhysicalBlockDevice(
                        node_config=node_config
                    )
                    filesystem = self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.RAID, block_device=block_device
                    )
                    group.filesystems.add(filesystem)
                spare_block_device = self.make_PhysicalBlockDevice(
                    node_config=node_config
                )
                spare_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.RAID_SPARE,
                    block_device=spare_block_device,
                )
                group.filesystems.add(spare_filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.BCACHE:
                backing_block_device = self.make_PhysicalBlockDevice(
                    node_config=node_config
                )
                backing_filesystem = self.make_Filesystem(
                    fstype=FILESYSTEM_TYPE.BCACHE_BACKING,
                    block_device=backing_block_device,
                )
                group.filesystems.add(backing_filesystem)
            elif group_type == FILESYSTEM_GROUP_TYPE.VMFS6:
                for _ in range(2):
                    partition = self.make_Partition(node=node)
                    self.make_Filesystem(
                        fstype=FILESYSTEM_TYPE.VMFS6,
                        partition=partition,
                        filesystem_group=group,
                    )
        else:
            for filesystem in filesystems:
                group.filesystems.add(filesystem)
        # Save again to make sure that the added filesystems are correct.
        group.save(force_update=True)
        return group

    def make_VolumeGroup(self, *args, **kwargs):
        if len(args) > 1:
            args[1] = FILESYSTEM_GROUP_TYPE.LVM_VG
        else:
            kwargs["group_type"] = FILESYSTEM_GROUP_TYPE.LVM_VG
        filesystem_group = self.make_FilesystemGroup(*args, **kwargs)
        return VolumeGroup.objects.get(id=filesystem_group.id)

    def make_VMFS(self, *args, **kwargs):
        return self.make_FilesystemGroup(
            *args, group_type=FILESYSTEM_GROUP_TYPE.VMFS6, **kwargs
        )

    def make_VMCluster(
        self,
        name=None,
        project=None,
        pods=1,
        vms=0,
        pool=None,
        zone=None,
        memory=4096,
        vm_memory=1024,
        cores=8,
        storage=None,
        disk_size=None,
    ):
        if name is None:
            name = self.make_name("name")
        if project is None:
            project = self.make_name("project")
        if zone is None:
            zone = Zone.objects.get_default_zone()

        cluster = VMCluster.objects.create(
            name=name,
            project=project,
            pool=pool,
            zone=zone,
        )

        for _ in range(0, pods):
            pod = self.make_Pod(
                pod_type="lxd",
                cores=cores,
                memory=memory,
                cluster=cluster,
                project=project,
            )
            pool = self.make_PodStoragePool(pod=pod, storage=storage)

            for _ in range(0, vms):
                node = self.make_Node(bmc=pod)
                vm = self.make_VirtualMachine(
                    machine=node,
                    memory=vm_memory,
                    pinned_cores=[0, 2],
                    hugepages_backed=False,
                    bmc=pod,
                    project=project,
                )
                self.make_VirtualMachineDisk(
                    vm=vm, backing_pool=pool, size=disk_size
                )

        return cluster

    def make_VirtualBlockDevice(
        self,
        name=None,
        size=None,
        block_size=None,
        tags=None,
        uuid=None,
        filesystem_group=None,
        node=None,
    ):
        if node is None:
            if filesystem_group is None:
                node = factory.make_Node()
            else:
                node = filesystem_group.get_node()
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        if filesystem_group is None:
            filesystem_group = self.make_FilesystemGroup(
                node=node,
                group_type=FILESYSTEM_GROUP_TYPE.LVM_VG,
                block_device_size=size,
                num_lvm_devices=2,
            )
        if size is None:
            available_size = filesystem_group.get_lvm_free_space()
            if available_size < MIN_BLOCK_DEVICE_SIZE:
                raise ValueError(
                    "Cannot make a virtual block device in filesystem_group; "
                    "not enough space."
                )
            size = round_size_to_nearest_block(
                random.randint(MIN_BLOCK_DEVICE_SIZE, available_size),
                block_size,
            )
        if tags is None:
            tags = [self.make_name("tag") for _ in range(3)]

        elif not filesystem_group.is_lvm():
            raise RuntimeError(
                "make_VirtualBlockDevice should only be used with "
                "filesystem_group that has a group_type of LVM_VG.  "
                "If you need a VirtualBlockDevice that is for another type "
                "use make_FilesystemGroup which will create a "
                "VirtualBlockDevice automatically."
            )
        if name is None:
            name = self.make_name("lv")
        if size is None:
            size = random.randint(1, filesystem_group.get_size())
        if block_size is None:
            block_size = random.choice([512, 1024, 4096])
        return VirtualBlockDevice.objects.create(
            node_config=node.current_config,
            name=name,
            size=size,
            block_size=block_size,
            tags=tags,
            uuid=uuid,
            filesystem_group=filesystem_group,
        )

    def make_DHCPSnippet(
        self,
        name=None,
        value=None,
        description=None,
        enabled=True,
        node=None,
        subnet=None,
        iprange=None,
    ):
        if name is None:
            name = self.make_name("dhcp_snippet")
        if value is None:
            value = VersionedTextFile.objects.create(data=self.make_string())
        if description is None:
            description = self.make_string()
        return DHCPSnippet.objects.create(
            name=name,
            value=value,
            description=description,
            enabled=enabled,
            node=node,
            subnet=subnet,
            iprange=iprange,
        )

    def make_default_PackageRepositories(self):
        factory.make_PackageRepository(
            name="main_archive",
            url="http://archive.ubuntu.com/ubuntu",
            default=True,
            arches=PackageRepository.MAIN_ARCHES,
        )
        factory.make_PackageRepository(
            name="ports_archive",
            url="http://ports.ubuntu.com/ubuntu-ports",
            default=True,
            arches=PackageRepository.PORTS_ARCHES,
        )

    def make_PackageRepository(
        self,
        name=None,
        url=None,
        arches=None,
        default=False,
        key=None,
        distributions=None,
        components=None,
        disabled_pockets=None,
        disabled_components=None,
        **kwargs,
    ):
        if name is None:
            name = self.make_name("name")
        if url is None:
            url = self.make_url(scheme="http")
        if arches is None:
            arches = random.sample(
                PackageRepository.KNOWN_ARCHES,
                random.randint(0, len(PackageRepository.KNOWN_ARCHES)),
            )
        if key is None:
            key = factory.make_name("key")
        return PackageRepository.objects.create(
            name=name,
            url=url,
            distributions=distributions,
            disabled_pockets=disabled_pockets,
            components=components,
            arches=arches,
            key=key,
            default=default,
            disabled_components=disabled_components,
            **kwargs,
        )

    def make_Notification(
        self,
        message=None,
        *,
        ident=None,
        user=None,
        users=False,
        admins=False,
        context=None,
        category=None,
        dismissable=True,
    ):
        if context is None:
            context_name = self.make_name("name")
            context = {context_name: self.make_name("value")}

        if message is None:
            context_names = [key for key in context if key.isidentifier()]
            if len(context_names) == 0:
                message = self.make_name("message")
            else:
                context_name = random.choice(context_names)
                message = self.make_name("message-{%s}" % context_name)

        if category is None:
            category = random.choice(("error", "warning", "success", "info"))

        notification = Notification(
            ident=ident,
            user=user,
            users=users,
            admins=admins,
            message=message,
            context=context,
            category=category,
            dismissable=dismissable,
        )
        notification.save()

        return notification

    def make_RootKey(self, material=None, expiration=None):
        if material is None:
            material = os.urandom(24)
        if expiration is None:
            expiration = datetime.now() + timedelta(days=1)
        key = RootKey.objects.create(expiration=expiration)
        SecretManager().set_simple_secret(
            "material", to_hex(material), obj=key
        )
        return key

    def make_PodStoragePool(
        self,
        pod=None,
        name=None,
        pool_id=None,
        pool_type=None,
        path=None,
        storage=None,
    ):
        if pod is None:
            pod = self.make_Pod()
        if name is None:
            name = self.make_name("name")
        if pool_id is None:
            pool_id = self.make_name("pool_id")
        if pool_type is None:
            pool_type = random.choice(["dir", "lvm"])
        if path is None:
            path = "/var/lib/%s" % name
        if storage is None:
            storage = random.randint(10 * 1024**3, 100 * 1024**3)
        return PodStoragePool.objects.create(
            pod=pod,
            name=name,
            pool_id=pool_id,
            pool_type=pool_type,
            path=path,
            storage=storage,
        )

    def make_NUMANode(self, node=None, cores=None, memory=None):
        if node is None:
            node = factory.make_Node()
        index = node.numanode_set.count()
        if cores is None:
            cores = list(range(2 ** random.randint(0, 4)))
        if memory is None:
            memory = 1024 * random.randint(1, 256)
        return NUMANode.objects.create(
            node=node, index=index, cores=cores, memory=memory
        )

    def make_NUMANodeHugepages(
        self, numa_node=None, page_size=None, total=None
    ):
        if numa_node is None:
            numa_node = self.make_NUMANode()
        if page_size is None:
            page_size = random.choice((2048, 1048576)) * 1024
        if total is None:
            total = random.randint(0, 16) * page_size
        return NUMANodeHugepages.objects.create(
            numanode=numa_node,
            page_size=page_size,
            total=total,
        )

    def make_NodeConfig(self, node=None, name=NODE_CONFIG_TYPE.DISCOVERED):
        if node is None:
            node = factory.make_Node()
            return node.current_config
        return NodeConfig.objects.create(node=node, name=name)

    def make_VirtualMachine(
        self,
        identifier=None,
        bmc=None,
        project="",
        machine=None,
        pinned_cores=None,
        unpinned_cores=0,
        memory=None,
        hugepages_backed=None,
    ):
        if identifier is None:
            identifier = factory.make_string(20)
        if bmc is None:
            bmc = factory.make_BMC(
                power_type="lxd",
                power_parameters={
                    "power_address": self.make_ip_address(),
                },
            )
        if pinned_cores is None:
            pinned_cores = []
            if unpinned_cores == 0 and machine is not None:
                unpinned_cores = machine.cpu_count
        if memory is None:
            if machine is None:
                memory = 0
            else:
                memory = machine.memory
        if hugepages_backed is None:
            hugepages_backed = self.pick_bool()
        return VirtualMachine.objects.create(
            identifier=identifier,
            bmc=bmc,
            project=project,
            hugepages_backed=hugepages_backed,
            memory=memory,
            machine=machine,
            pinned_cores=pinned_cores,
            unpinned_cores=unpinned_cores,
        )

    def make_VirtualMachineDisk(
        self,
        vm=None,
        name=None,
        size=None,
        block_device=None,
        backing_pool=None,
    ):
        if vm is None:
            vm = factory.make_VirtualMachine()
        if name is None:
            name = factory.make_name("vmdisk")
        if size is None:
            size = random.randint(
                MIN_BLOCK_DEVICE_SIZE * 4, MIN_BLOCK_DEVICE_SIZE * 1024
            )
        return VirtualMachineDisk.objects.create(
            name=name,
            vm=vm,
            size=size,
            block_device=block_device,
            backing_pool=backing_pool,
        )

    def make_NodeDevice(
        self,
        bus=None,
        hardware_type=None,
        node_config=None,
        node=None,
        numa_node=None,
        physical_blockdevice=None,
        physical_interface=None,
        vendor_id=None,
        vendor_name=None,
        product_id=None,
        product_name=None,
        commissioning_driver=None,
        bus_number=None,
        device_number=None,
        pci_address=None,
        **kwargs,
    ):
        if bus is None:
            bus = factory.pick_choice(NODE_DEVICE_BUS_CHOICES)
        if hardware_type is None:
            hardware_type = factory.pick_choice(
                HARDWARE_TYPE_CHOICES,
                but_not=(
                    # Storage and network NodeDevices are created in
                    # make_PhysicalBlockDevice and make_Interface
                    HARDWARE_TYPE.STORAGE,
                    HARDWARE_TYPE.NETWORK,
                ),
            )
        if node_config is None:
            if node is None:
                node_config = factory.make_NodeConfig()
            else:
                node_config = node.current_config
        # ensure it's always set
        node = node_config.node
        if numa_node is None:
            try:
                numa_node = random.choice(node.numanode_set.all())
            except IndexError:
                numa_node = factory.make_NUMANode(node=node)
        if vendor_id is None:
            vendor_id = self.make_hex_string(size=4)
        if vendor_name is None:
            vendor_name = self.make_name("vendor_name")
        if product_id is None:
            product_id = self.make_hex_string(size=4)
        if product_name is None:
            product_name = self.make_name("product_name")
        if commissioning_driver is None:
            commissioning_driver = self.make_name("commissioning_driver")
        if bus_number is None:
            bus_number = random.randint(0, 2**16)
        if device_number is None:
            device_number = random.randint(0, 2**16)
        if pci_address is None and bus == NODE_DEVICE_BUS.PCIE:
            pci_domain = factory.make_hex_string(size=4)
            pci_function_number = random.randint(0, 9)
            pci_address = (
                f"{pci_domain}:{hex(bus_number)[2:].zfill(2)}"
                f":{hex(device_number)[2:].zfill(2)}.{pci_function_number}"
            )
        return NodeDevice.objects.create(
            bus=bus,
            hardware_type=hardware_type,
            node_config=node_config,
            numa_node=numa_node,
            physical_blockdevice=physical_blockdevice,
            physical_interface=physical_interface,
            vendor_id=vendor_id,
            vendor_name=vendor_name,
            product_id=product_id,
            product_name=product_name,
            commissioning_driver=commissioning_driver,
            bus_number=bus_number,
            device_number=device_number,
            pci_address=pci_address,
            **kwargs,
        )

    def make_NodeDeviceVPD(
        self, node_device=None, key=None, value=None, **kwargs
    ):
        if node_device is None:
            owner = get_worker_user()
            node = self.make_Node(
                owner=owner, node_type=NODE_TYPE.MACHINE, **kwargs
            )
            node.save()
            node_device = self.make_NodeDevice(
                bus=NODE_DEVICE_BUS.PCIE,
                hardware_type=HARDWARE_TYPE.NETWORK,
                node=node,
            )
            node_device.save()

        if key is None:
            key = self.make_name(size=2)
        if value is None:
            value = self.make_string(prefix="value", spaces=True)
        metadata = NodeDeviceVPD.objects.create(
            node_device=node_device, key=key, value=value
        )
        return metadata

    def make_BMCRoutableRackControllerRelationship(self, bmc, rack):
        BMCRoutableRackControllerRelationship(
            bmc=bmc, rack_controller=rack, routable=True
        ).save()


# Create factory singleton.
factory = Factory()
