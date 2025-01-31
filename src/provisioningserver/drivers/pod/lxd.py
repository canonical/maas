# Copyright 2020-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD Pod Driver."""


from contextlib import contextmanager, suppress
import os
from pathlib import Path
import re
from typing import Optional, Tuple
from urllib.parse import urlparse
import uuid

from pylxd import Client
from pylxd.client import get_session_for_url
from pylxd.exceptions import ClientConnectionFailed, LXDAPIException, NotFound
import urllib3

from provisioningserver.certificates import (
    Certificate,
    CertificateError,
    get_maas_cert_tuple,
)
from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.pod import (
    Capabilities,
    DiscoveredCluster,
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    DiscoveredPodStoragePool,
    InterfaceAttachType,
    PodDriver,
    RequestedMachine,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.refresh.node_info_scripts import (
    COMMISSIONING_OUTPUT_NAME,
    RUN_MACHINE_RESOURCES,
)
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils.arch import (
    debian_to_kernel_architecture,
    kernel_to_debian_architecture,
)
from provisioningserver.utils.lxd import lxd_cpu_speed
from provisioningserver.utils.network import generate_mac_address
from provisioningserver.utils.twisted import asynchronous, threadDeferred

# silence warnings from pylxd because of unverified certs for HTTPS connection
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


maaslog = get_maas_logger("drivers.pod.lxd")

LXD_MAAS_PROFILE = "maas"

# LXD status codes
LXD_VM_POWER_STATE = {101: "on", 102: "off", 103: "on", 110: "off"}

# LXD byte suffixes.
# https://lxd.readthedocs.io/en/latest/instances/#units-for-storage-and-network-limits
LXD_BYTE_SUFFIXES = {
    "B": 1,
    "kB": 1000,
    "MB": 1000**2,
    "GB": 1000**3,
    "TB": 1000**4,
    "PB": 1000**5,
    "EB": 1000**6,
    "KiB": 1024,
    "MiB": 1024**2,
    "GiB": 1024**3,
    "TiB": 1024**4,
    "PiB": 1024**5,
    "EiB": 1024**6,
}

LXD_REQUIRED_EXTENSIONS = frozenset(
    ("projects", "virtual-machines", "custom_block_volumes")
)

LXD_MIN_VERSION = "4.16"


def convert_lxd_byte_suffixes(value, divisor=None):
    """Takes the value and converts to a proper integer
    using LXD_BYTE_SUFFIXES."""
    value = str(value)
    result = re.match(
        r"(?P<size>[0-9]+)(?P<unit>%s)" % "|".join(LXD_BYTE_SUFFIXES.keys()),
        value,
    )
    if result is not None:
        value = result.group("size")
        if "." in value:
            value = float(value)
        value = float(value) * LXD_BYTE_SUFFIXES[result.group("unit")]
    if divisor:
        value = float(value) / divisor
    return int(value)


def get_lxd_nic_device(name, interface, default_parent):
    """Convert a RequestedMachineInterface into a LXD device definition."""
    parent = interface.attach_name
    nictype = interface.attach_type
    if not parent:
        parent = default_parent.attach_name
        nictype = default_parent.attach_type

    # LXD uses 'bridged' while MAAS uses 'bridge' so convert the nictype.
    if nictype == InterfaceAttachType.BRIDGE:
        nictype = "bridged"

    device = {
        "name": name,
        "nictype": nictype,
        "parent": parent,
        "type": "nic",
    }
    if interface.attach_type == InterfaceAttachType.SRIOV:
        device["hwaddr"] = generate_mac_address()
    if interface.attach_vlan is not None:
        device["vlan"] = str(interface.attach_vlan)
    return device


def get_lxd_machine_definition(request, include_profile=False):
    profiles = []
    if include_profile:
        profiles.append(LXD_MAAS_PROFILE)
    return {
        "name": request.hostname,
        "architecture": debian_to_kernel_architecture(request.architecture),
        "config": {
            "limits.cpu": _get_cpu_limits(request),
            "limits.memory": str(request.memory * 1024**2),
            "limits.memory.hugepages": (
                "true" if request.hugepages_backed else "false"
            ),
            # LP: 1867387 - Disable secure boot until its fixed in MAAS
            "security.secureboot": "false",
        },
        "profiles": profiles,
        # Image source is empty as we get images from MAAS when netbooting.
        "source": {"type": "none"},
    }


def _get_lxd_network_states(client):
    networks = {}
    for net in client.networks.all():
        try:
            state = net.state()
        except NotFound:
            # Some interfaces might have gone away since we
            # listed them. This happens when VM restarts or
            # stops, for example.
            continue
        except LXDAPIException as api_error:
            # Need to catch LXDAPIException due to
            # https://github.com/canonical/lxd/issues/9191
            if str(api_error).endswith("not found"):
                continue
            else:
                raise
        else:
            networks[net.name] = dict(state)
    return networks


class LXDPodError(Exception):
    """Failure communicating to LXD."""


class LXDPodDriver(PodDriver):
    name = "lxd"
    chassis = True
    can_probe = False
    can_set_boot_order = False
    description = "LXD (virtual systems)"
    settings = [
        make_setting_field(
            "power_address",
            "LXD address",
            field_type="lxd_address",
            required=True,
        ),
        make_setting_field(
            "instance_name",
            "Instance name",
            scope=SETTING_SCOPE.NODE,
            required=True,
        ),
        make_setting_field(
            "project",
            "LXD project",
            required=True,
            default="default",
        ),
        make_setting_field(
            "password",
            "LXD password (optional)",
            required=False,
            field_type="password",
            secret=True,
        ),
        make_setting_field(
            "certificate",
            "LXD certificate (optional)",
            required=False,
        ),
        make_setting_field(
            "key",
            "LXD private key (optional)",
            required=False,
            field_type="password",
            secret=True,
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    _pylxd_client_class = Client

    def detect_missing_packages(self):
        # python3-pylxd is a required package
        # for maas and is installed by default.
        return []

    def get_url(self, context: dict):
        """Return url for the LXD host."""
        power_address = context.get("power_address")
        if "://" not in power_address:
            # must have a scheme to be a valid URL
            power_address = f"https://{power_address}"
        url = urlparse(power_address)
        if not url.port:
            url = url._replace(netloc=f"{url.netloc}:8443")
        return url.geturl()

    @asynchronous
    @threadDeferred
    def power_on(self, pod_id: int, context: dict):
        """Power on LXD VM."""
        with self._get_machine(pod_id, context) as machine:
            power_state = LXD_VM_POWER_STATE[machine.status_code]
            maaslog.debug(f"power_on: {pod_id} is {power_state}")
            if power_state == "off":
                machine.start()

    @asynchronous
    @threadDeferred
    def power_off(self, pod_id: int, context: dict):
        """Power off LXD VM."""
        with self._get_machine(pod_id, context) as machine:
            power_state = LXD_VM_POWER_STATE[machine.status_code]
            maaslog.debug(f"power_off: {pod_id} is {power_state}")
            if power_state == "on":
                machine.stop()

    @asynchronous
    @threadDeferred
    def power_query(self, pod_id: int, context: dict):
        """Power query LXD VM."""
        with self._get_machine(pod_id, context) as machine:
            state = machine.status_code
            try:
                return LXD_VM_POWER_STATE[state]
            except KeyError:
                raise LXDPodError(
                    f"Pod {pod_id}: Unknown power status code: {state}"
                )

    @asynchronous
    @threadDeferred
    def power_reset(self, pod_id: int, context: dict):
        """Power reset LXD VM."""
        raise NotImplementedError()

    @threadDeferred
    def discover_projects(self, pod_id: int, context: dict):
        """Discover the list of projects in a pod."""
        with self._get_client(pod_id, context) as client:
            self._check_required_extensions(client)
            return [
                {"name": project.name, "description": project.description}
                for project in client.projects.all()
            ]

    @threadDeferred
    def discover(self, pod_id: int, context: dict):
        """Discover all Pod host resources."""
        with self._get_client(pod_id, context) as client:
            discovered_pod = self._discover(client, pod_id, context)
            if discovered_pod.clustered:
                return self._discover_cluster(client, context)
            return discovered_pod

    def _discover_cluster(self, client: Client, context: dict):
        discovered_cluster = DiscoveredCluster(
            name=context.get("instance_name"),
            project=client.project,
        )

        cluster_members = client.cluster.members.all()

        for member in cluster_members:
            discovered_context = context.copy()
            discovered_context["instance_name"] = member.server_name
            discovered_context["power_address"] = member.url
            with self._get_client(-1, discovered_context) as client:
                discovered_cluster.pods.append(
                    self._discover(client, -1, discovered_context)
                )
                discovered_cluster.pod_addresses.append(member.url)
        return discovered_cluster

    def _discover(self, client: Client, pod_id: int, context: dict):
        self._check_required_extensions(client)

        if not client.trusted:
            # return empty information as the client is not authenticated and
            # gathering other info requires auth.
            return DiscoveredPod()

        self._ensure_project(client)

        environment = client.host_info["environment"]
        # After the region creates the Pod object it will sync LXD commissioning
        # data for all hardware information.
        discovered_pod = DiscoveredPod(
            # client.host_info["environment"]["architectures"] reports all the
            # architectures the host CPU supports, not the architectures LXD
            # supports. On x86_64 LXD reports [x86_64, i686] however LXD does
            # not currently support VMs on i686. The LXD API currently does not
            # have a way to query which architectures are usable for VMs. The
            # safest bet is to just use the kernel_architecture.
            architectures=[
                kernel_to_debian_architecture(
                    environment["kernel_architecture"]
                )
            ],
            name=environment["server_name"],
            version=environment["server_version"],
            capabilities=[
                Capabilities.COMPOSABLE,
                Capabilities.DYNAMIC_LOCAL_STORAGE,
                Capabilities.OVER_COMMIT,
                Capabilities.STORAGE_POOLS,
            ],
            clustered=environment["server_clustered"],
        )

        # Discover networks. "unknown" interfaces are considered too to match
        # ethernets in containers.
        networks_state = [
            net.state()
            for net in client.networks.all()
            if net.type in ("unknown", "physical")
        ]
        discovered_pod.mac_addresses = list(
            {state.hwaddr for state in networks_state if state.hwaddr}
        )

        # Discover storage pools.
        storage_pools = client.storage_pools.all()
        if not storage_pools:
            raise LXDPodError(
                "No storage pools exists.  Please create a storage pool in LXD."
            )
        pools = []
        local_storage = 0
        for storage_pool in storage_pools:
            discovered_storage_pool = self._get_discovered_storage_pool(
                storage_pool
            )
            local_storage += discovered_storage_pool.storage
            pools.append(discovered_storage_pool)
        discovered_pod.storage_pools = pools
        discovered_pod.local_storage = local_storage

        # Discover VMs.
        host_cpu_speed = lxd_cpu_speed(client.resources)
        projects = [project.name for project in client.projects.all()]
        machines = []
        for project in projects:
            with self._get_client(
                pod_id, context, project=project
            ) as project_cli:
                for virtual_machine in project_cli.virtual_machines.all():
                    discovered_machine = self._get_discovered_machine(
                        project_cli,
                        virtual_machine,
                        storage_pools=discovered_pod.storage_pools,
                    )
                    discovered_machine.cpu_speed = host_cpu_speed
                    machines.append(discovered_machine)
        discovered_pod.machines = machines

        return discovered_pod

    @threadDeferred
    def get_commissioning_data(self, pod_id: int, context: dict):
        """Retreive commissioning data from LXD."""
        with self._get_client(pod_id, context) as client:
            resources = {
                # /1.0
                **client.host_info,
                # /1.0/resources
                "resources": client.resources,
                # /1.0/networks/<network>/state
                "networks": _get_lxd_network_states(client),
            }
        # return the output for both scripts to match what commissioning does
        return {
            RUN_MACHINE_RESOURCES: resources,
            COMMISSIONING_OUTPUT_NAME: resources,
        }

    @threadDeferred
    def compose(self, pod_id: int, context: dict, request: RequestedMachine):
        """Compose a virtual machine."""
        with self._get_client(pod_id, context) as client:
            self._check_required_extensions(client)

            storage_pools = client.storage_pools.all()
            default_storage_pool = context.get(
                "default_storage_pool_id", context.get("default_storage_pool")
            )

            include_profile = client.profiles.exists(LXD_MAAS_PROFILE)
            definition = get_lxd_machine_definition(
                request, include_profile=include_profile
            )
            definition["devices"] = {
                **self._get_machine_disks(
                    request.block_devices, storage_pools, default_storage_pool
                ),
                **self._get_machine_nics(request),
            }

            # Create the machine.
            create_kwargs = {"wait": True}
            if client.host_info["environment"]["server_clustered"]:
                create_kwargs["target"] = client.host_info["environment"][
                    "server_name"
                ]

            machine = client.virtual_machines.create(
                definition, **create_kwargs
            )
            # Pod hints are updated on the region after the machine is composed.
            discovered_machine = self._get_discovered_machine(
                client, machine, storage_pools, request=request
            )
            # Update the machine cpu speed.
            discovered_machine.cpu_speed = lxd_cpu_speed(client.resources)
            return discovered_machine, DiscoveredPodHints()

    @threadDeferred
    def decompose(self, pod_id: int, context: dict):
        """Decompose a virtual machine."""
        with self._get_machine(pod_id, context) as machine:
            if not machine:
                maaslog.warning(
                    f"Pod {pod_id}: machine {context['instance_name']} not found"
                )
                return DiscoveredPodHints()

            if machine.status_code != 102:  # 102 - Stopped
                machine.stop(force=True, wait=True)
            # collect machine attributes before removing it
            devices = machine.devices
            client = machine.client
            machine.delete(wait=True)
            self._delete_machine_volumes(client, pod_id, devices)
            # Hints are updated on the region for LXDPodDriver.
            return DiscoveredPodHints()

    def _check_required_extensions(self, client):
        """Raise an error if the LXD server doesn't support all required features."""
        all_extensions = set(client.host_info["api_extensions"])
        missing_extensions = sorted(LXD_REQUIRED_EXTENSIONS - all_extensions)
        if missing_extensions:
            raise LXDPodError(
                f"Please upgrade your LXD host to {LXD_MIN_VERSION} or higher "
                f"to support the following extensions: {','.join(missing_extensions)}"
            )

    def _get_machine_disks(
        self, requested_disks, storage_pools, default_storage_pool
    ):
        """Return definitions for machine disks, after creating needed volumes."""
        disks = {}
        for idx, disk in enumerate(requested_disks):
            pool = self._get_usable_storage_pool(
                disk, storage_pools, default_storage_pool
            )
            size = str(disk.size)
            if idx == 0:
                label = "root"
                path = "/"
                extra_conf = {
                    "boot.priority": "0",
                    "size": size,
                }
            else:
                label = f"disk{idx}"
                path = ""
                volume = self._create_volume(pool, size)
                extra_conf = {"source": volume.name}
            disks[label] = {
                "path": path,
                "type": "disk",
                "pool": pool.name,
                **extra_conf,
            }
        return disks

    def _get_machine_nics(self, request):
        default_parent = self.get_default_interface_parent(
            request.known_host_interfaces
        )
        if default_parent is None:
            raise LXDPodError("No host network to attach VM interfaces to")

        nics = {}
        ifnames = {
            iface.ifname for iface in request.interfaces if iface.ifname
        }
        ifindex = 0
        for idx, interface in enumerate(request.interfaces):
            ifname = interface.ifname
            if ifname is None:
                # get the next available interface name
                ifname = f"eth{ifindex}"
                while ifname in ifnames:
                    ifindex += 1
                    ifname = f"eth{ifindex}"
                ifnames.add(ifname)

            nic = get_lxd_nic_device(ifname, interface, default_parent)
            # Set to boot from the first nic
            if idx == 0:
                nic["boot.priority"] = "1"
            nics[ifname] = nic
        return nics

    @PROMETHEUS_METRICS.failure_counter("maas_lxd_disk_creation_failure")
    def _create_volume(self, pool, size):
        """Create a storage volume."""
        name = f"maas-{uuid.uuid4()}"
        return pool.volumes.create(
            "custom",
            {"name": name, "content_type": "block", "config": {"size": size}},
        )

    def _delete_machine_volumes(self, client, pod_id: int, devices: dict):
        """Delete machine volumes.

        The VM root volume is not removed as it's handled automatically by LXD.
        """
        for device in devices.values():
            source = device.get("source")
            if device["type"] != "disk" or not source:
                continue
            pool_name = device["pool"]
            try:
                pool = client.storage_pools.get(pool_name)
                pool.volumes.get("custom", source).delete()
            except Exception:
                maaslog.warning(
                    f"Pod {pod_id}: failed to delete volume {source} in pool {pool_name}"
                )

    def _ensure_project(self, client):
        """Ensure the project that the client is configured with exists."""
        if client.projects.exists(client.project):
            return
        client.projects.create(
            name=client.project, description="Project managed by MAAS"
        )

    def _get_usable_storage_pool(
        self, disk, storage_pools, default_storage_pool=None
    ):
        """Return the storage pool and type that has enough space for `disk.size`."""
        # Filter off of tags.
        filtered_storage_pools = [
            storage_pool
            for storage_pool in storage_pools
            if storage_pool.name in disk.tags
        ]
        if filtered_storage_pools:
            for storage_pool in filtered_storage_pools:
                resources = storage_pool.resources.get()
                available = resources.space["total"] - resources.space["used"]
                if disk.size <= available:
                    return storage_pool
            raise PodInvalidResources(
                "Not enough storage space on storage pools: %s"
                % (
                    ", ".join(
                        [
                            storage_pool.name
                            for storage_pool in filtered_storage_pools
                        ]
                    )
                )
            )
        # Filter off of default storage pool name.
        if default_storage_pool:
            filtered_storage_pools = [
                storage_pool
                for storage_pool in storage_pools
                if storage_pool.name == default_storage_pool
            ]
            if filtered_storage_pools:
                default_storage_pool = filtered_storage_pools[0]
                resources = default_storage_pool.resources.get()
                available = resources.space["total"] - resources.space["used"]
                if disk.size <= available:
                    return default_storage_pool
                raise PodInvalidResources(
                    f"Not enough space in default storage pool: {default_storage_pool.name}"
                )
            raise LXDPodError(
                f"Default storage pool '{default_storage_pool}' doesn't exist."
            )

        # No filtering, just find a storage pool with enough space.
        for storage_pool in storage_pools:
            resources = storage_pool.resources.get()
            available = resources.space["total"] - resources.space["used"]
            if disk.size <= available:
                return storage_pool
        raise PodInvalidResources(
            "Not enough storage space on any storage pools: %s"
            % (
                ", ".join(
                    [storage_pool.name for storage_pool in storage_pools]
                )
            )
        )

    def _get_discovered_machine(
        self, client, machine, storage_pools, request=None
    ):
        """Get the discovered machine."""
        # Check the power state first.
        state = machine.status_code
        try:
            power_state = LXD_VM_POWER_STATE[state]
        except KeyError:
            maaslog.error(
                f"{machine.name}: Unknown power status code: {state}"
            )
            power_state = "unknown"

        def _get_discovered_block_device(name, device, requested_device=None):
            tags = requested_device.tags if requested_device else []
            # When LXD creates a QEMU disk the serial is always lxd_{device
            # name}. The device name is commonly "root" for the first disk. The
            # model and serial must be correctly defined here otherwise MAAS
            # will delete the disk created during composition which results in
            # losing the storage pool link. Without the storage pool link MAAS
            # can't determine how much of the storage pool has been used.
            serial = f"lxd_{name}"
            source = device.get("source")
            pool = device.get("pool")  # not set for e.g. file-backed devices
            if source and pool:
                storage_pool = client.storage_pools.get(pool)
                volume = storage_pool.volumes.get("custom", source)
                size = volume.config.get("size")
            else:
                size = device.get("size")
            # Default disk size is 10GB in LXD
            size = convert_lxd_byte_suffixes(size or "10GB")
            return DiscoveredMachineBlockDevice(
                model="QEMU HARDDISK",
                serial=serial,
                id_path=f"/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_{serial}",
                size=size,
                tags=tags,
                storage_pool=device.get("pool"),
            )

        expanded_config = machine.expanded_config
        iface_to_mac = {
            key.split(".")[1]: value
            for key, value in expanded_config.items()
            if key.endswith("hwaddr")
        }

        def _get_discovered_interface(name, device, boot):
            if "network" in device:
                # Try finding the nictype from the networks.
                # XXX: This should work for "bridge" networks,
                #      but will most likely produce weird results for the
                #      other types.
                network = client.networks.get(device["network"])
                attach_type = network.type
                attach_name = network.name
            else:
                attach_name = device["parent"]
                nictype = device["nictype"]
                attach_type = (
                    InterfaceAttachType.BRIDGE
                    if nictype == "bridged"
                    else nictype
                )
            mac = device.get("hwaddr")
            if mac is None:
                mac = iface_to_mac.get(name)
            return DiscoveredMachineInterface(
                mac_address=mac,
                vid=int(device.get("vlan", 0)),
                boot=boot,
                attach_type=attach_type,
                attach_name=attach_name,
            )

        extra_block_devices = 0
        block_devices = []
        interfaces = []
        for name, device in machine.expanded_devices.items():
            if device["type"] == "disk":
                requested_device = None
                index = -1
                if request:
                    # for composed VMs, the root disk is always the first
                    # one. Adjust the index so that it matches the requested
                    # device
                    if name == "root":
                        index = 0
                    else:
                        extra_block_devices += 1
                        index = extra_block_devices
                    requested_device = request.block_devices[index]

                blkdev = _get_discovered_block_device(
                    name, device, requested_device=requested_device
                )

                if index >= 0:
                    block_devices.insert(index, blkdev)
                else:
                    block_devices.append(blkdev)

            elif device["type"] == "nic":
                interfaces.append(
                    _get_discovered_interface(name, device, not interfaces)
                )

        # LXD uses different suffixes to store memory so make
        # sure we convert to MiB, which is what MAAS uses.
        memory = expanded_config.get("limits.memory")
        if memory is not None:
            memory = convert_lxd_byte_suffixes(memory, divisor=1024**2)
        else:
            memory = 1024
        hugepages_backed = _get_bool(
            expanded_config.get("limits.memory.hugepages")
        )
        cores, pinned_cores = _parse_cpu_cores(
            expanded_config.get("limits.cpu")
        )
        return DiscoveredMachine(
            hostname=machine.name,
            architecture=kernel_to_debian_architecture(machine.architecture),
            # 1 core and 1GiB of memory (we need it in MiB) is default for
            # LXD if not specified.
            cores=cores,
            memory=memory,
            cpu_speed=0,
            interfaces=interfaces,
            block_devices=block_devices,
            power_state=power_state,
            power_parameters={
                "instance_name": machine.name,
                "project": client.project,
            },
            tags=[],
            hugepages_backed=hugepages_backed,
            pinned_cores=pinned_cores,
            # LXD VMs use only UEFI.
            bios_boot_method="uefi",
            location=machine.location,
        )

    def _get_discovered_storage_pool(self, storage_pool):
        """Get storage pool info by name."""
        # Storage configuration can either be empty or None (if credentials are
        # restricted to a project)
        storage_pool_config = storage_pool.config or {}
        storage_pool_path = storage_pool_config.get("source", "Unknown")
        storage_pool_resources = storage_pool.resources.get()
        total_storage = storage_pool_resources.space["total"]

        return DiscoveredPodStoragePool(
            id=storage_pool.name,
            name=storage_pool.name,
            path=storage_pool_path,
            type=storage_pool.driver,
            storage=total_storage,
        )

    @PROMETHEUS_METRICS.failure_counter("maas_lxd_fetch_machine_failure")
    @contextmanager
    def _get_machine(self, pod_id: int, context: dict, fail: bool = True):
        """Retrieve LXD VM.

        If "fail" is False, return None instead of raising an exception.
        """
        instance_name = context.get("instance_name")
        with self._get_client(pod_id, context) as client:
            try:
                yield client.virtual_machines.get(instance_name)
            except NotFound:
                if fail:
                    raise LXDPodError(
                        f"Pod {pod_id}: LXD VM {instance_name} not found."
                    )
                yield None

    @contextmanager
    def _get_client(
        self,
        pod_id: int,
        context: dict,
        project: Optional[str] = None,
    ):
        """Return a context manager with a PyLXD client."""

        def Error(message):
            return LXDPodError(f"VM Host {pod_id}: {message}")

        endpoint = self.get_url(context)
        if not project:
            project = context.get("project", "default")

        password = context.get("password")
        try:
            cert_paths = self._get_cert_paths(context)
        except CertificateError as e:
            raise Error(str(e))
        maas_certs = get_maas_cert_tuple()
        if not cert_paths and not maas_certs:
            raise Error("No certificates available")

        def client_with_certs(cert):
            session = get_session_for_url(endpoint, cert=cert, verify=False)
            # Don't inherit proxy environment variables
            session.trust_env = False
            client = self._pylxd_client_class(
                endpoint=endpoint,
                project=project,
                cert=cert,
                verify=False,
                session=session,
            )
            if not client.trusted and password:
                try:
                    client.authenticate(password)
                except LXDAPIException as e:
                    raise Error(f"Password authentication failed: {e}") from e
            return client

        try:
            if cert_paths:
                client = client_with_certs(cert_paths)
                if not client.trusted and maas_certs:
                    with suppress(LXDAPIException):
                        # Try to trust the certificate using the controller
                        # certs. If this fails, ignore the error as the trusted
                        # status for the original client is checked later.
                        client_with_certs(maas_certs).certificates.create(
                            "", Path(cert_paths[0]).read_bytes()
                        )
                        # create a new client since the certs are now trusted
                        client = client_with_certs(cert_paths)
            else:
                client = client_with_certs(maas_certs)

            if not client.trusted:
                raise Error(
                    "Certificate is not trusted and no password was given"
                )
        except ClientConnectionFailed as e:
            raise LXDPodError(
                f"Pod {pod_id}: Failed to connect to the LXD REST API: {e}"
            ) from e
        else:
            yield client
        finally:
            for path in cert_paths:
                os.unlink(path)

    def _get_cert_paths(self, context: dict) -> Optional[Tuple[str, str]]:
        """Return a 2-tuple with paths for temporary files containing cert and key.

        If no certificate or key are provided, an empty tuple is returned.

        If invalid material is passed, an error is raised.
        """
        cert = context.get("certificate")
        key = context.get("key")
        if not cert or not key:
            return ()

        cert = Certificate.from_pem(cert, key)
        return cert.tempfiles()


def _parse_cpu_cores(cpu_limits):
    """Return number of vCPUs and list of pinned cores."""
    if not cpu_limits:
        return 1, []
    with suppress(ValueError):
        return int(cpu_limits), []

    pinned_cores = []
    for cores_range in cpu_limits.split(","):
        if "-" in cores_range:
            start, end = cores_range.split("-")
            pinned_cores.extend(range(int(start), int(end) + 1))
        else:
            pinned_cores.append(int(cores_range))
    return len(pinned_cores), sorted(pinned_cores)


def _get_cpu_limits(request):
    """Return the `limits.cpu` entry from the request cores configuration."""
    pinned_cores = request.pinned_cores
    if pinned_cores:
        if len(pinned_cores) == 1:
            limits_cpu = f"{pinned_cores[0]}-{pinned_cores[0]}"
        else:
            limits_cpu = ",".join(str(core) for core in pinned_cores)
    else:
        limits_cpu = str(request.cores)
    return limits_cpu


def _get_bool(value):
    """Convert the given LXD config value to a bool."""
    if not value:
        return False
    return value.lower() in ("true", "1")
