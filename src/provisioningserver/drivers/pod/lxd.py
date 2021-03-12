# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD Pod Driver."""


from contextlib import suppress
import re
from typing import Optional
from urllib.parse import urlparse
import uuid

from pylxd import Client
from pylxd.exceptions import ClientConnectionFailed, NotFound
import urllib3

from provisioningserver.drivers import (
    IP_EXTRACTOR_PATTERNS,
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.pod import (
    Capabilities,
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
from provisioningserver.maas_certificates import get_maas_cert_tuple
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils import (
    debian_to_kernel_architecture,
    kernel_to_debian_architecture,
    typed,
)
from provisioningserver.utils.ipaddr import get_vid_from_ifname
from provisioningserver.utils.lxd import lxd_cpu_speed
from provisioningserver.utils.network import generate_mac_address
from provisioningserver.utils.twisted import asynchronous, threadDeferred

# silence warnings from pylxd because of unverified certs for HTTPS connection
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


maaslog = get_maas_logger("drivers.pod.lxd")

# LXD status codes
LXD_VM_POWER_STATE = {101: "on", 102: "off", 103: "on", 110: "off"}


# LXD byte suffixes.
# https://lxd.readthedocs.io/en/latest/instances/#units-for-storage-and-network-limits
LXD_BYTE_SUFFIXES = {
    "B": 1,
    "kB": 1000,
    "MB": 1000 ** 2,
    "GB": 1000 ** 3,
    "TB": 1000 ** 4,
    "PB": 1000 ** 5,
    "EB": 1000 ** 6,
    "KiB": 1024,
    "MiB": 1024 ** 2,
    "GiB": 1024 ** 3,
    "TiB": 1024 ** 4,
    "PiB": 1024 ** 5,
    "EiB": 1024 ** 6,
}


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


def get_lxd_nic_device(interface):
    """Convert a RequestedMachineInterface into a LXD device definition."""
    # LXD uses 'bridged' while MAAS uses 'bridge' so convert
    # the nictype.
    nictype = (
        "bridged"
        if interface.attach_type == InterfaceAttachType.BRIDGE
        else interface.attach_type
    )
    device = {
        "name": interface.ifname,
        "parent": interface.attach_name,
        "nictype": nictype,
        "type": "nic",
    }
    if interface.attach_type == InterfaceAttachType.SRIOV:
        device["hwaddr"] = generate_mac_address()
    if interface.attach_vlan is not None:
        device["vlan"] = str(interface.attach_vlan)
    return device


def get_lxd_machine_definition(request, profile_name):
    return {
        "name": request.hostname,
        "architecture": debian_to_kernel_architecture(request.architecture),
        "config": {
            "limits.cpu": _get_cpu_limits(request),
            "limits.memory": str(request.memory * 1024 ** 2),
            "limits.memory.hugepages": "true"
            if request.hugepages_backed
            else "false",
            # LP: 1867387 - Disable secure boot until its fixed in MAAS
            "security.secureboot": "false",
        },
        "profiles": [profile_name],
        # Image source is empty as we get images from MAAS when netbooting.
        "source": {"type": "none"},
    }


class LXDPodError(Exception):
    """Failure communicating to LXD. """


class LXDPodDriver(PodDriver):

    name = "lxd"
    chassis = True
    can_probe = False
    description = "LXD (virtual systems)"
    settings = [
        make_setting_field("power_address", "LXD address", required=True),
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
        ),
    ]
    ip_extractor = make_ip_extractor(
        "power_address", IP_EXTRACTOR_PATTERNS.URL
    )

    def detect_missing_packages(self):
        # python3-pylxd is a required package
        # for maas and is installed by default.
        return []

    @typed
    def get_url(self, context: dict):
        """Return url for the LXD host."""
        power_address = context.get("power_address")
        url = urlparse(power_address)
        if not url.scheme:
            # When the scheme is not included in the power address
            # urlparse puts the url into path.
            url = url._replace(scheme="https", netloc="%s" % url.path, path="")
        if not url.port:
            if url.netloc:
                url = url._replace(netloc="%s:8443" % url.netloc)
            else:
                # Similar to above, we need to swap netloc and path.
                url = url._replace(netloc="%s:8443" % url.path, path="")

        return url.geturl()

    @typed
    @asynchronous
    @threadDeferred
    def power_on(self, pod_id: int, context: dict):
        """Power on LXD VM."""
        machine = self._get_machine(pod_id, context)
        if LXD_VM_POWER_STATE[machine.status_code] == "off":
            machine.start()

    @typed
    @asynchronous
    @threadDeferred
    def power_off(self, pod_id: int, context: dict):
        """Power off LXD VM."""
        machine = self._get_machine(pod_id, context)
        if LXD_VM_POWER_STATE[machine.status_code] == "on":
            machine.stop()

    @typed
    @asynchronous
    @threadDeferred
    def power_query(self, pod_id: int, context: dict):
        """Power query LXD VM."""
        machine = self._get_machine(pod_id, context)
        state = machine.status_code
        try:
            return LXD_VM_POWER_STATE[state]
        except KeyError:
            raise LXDPodError(
                f"Pod {pod_id}: Unknown power status code: {state}"
            )

    @threadDeferred
    def discover_projects(self, pod_id: int, context: dict):
        """Discover the list of projects in a pod."""
        client = self._get_client(pod_id, context)
        if not client.has_api_extension("projects"):
            raise LXDPodError(
                "Please upgrade your LXD host to 3.6+ for projects support."
            )
        return [
            {"name": project.name, "description": project.description}
            for project in client.projects.all()
        ]

    @threadDeferred
    def discover(self, pod_id: int, context: dict):
        """Discover all Pod host resources."""
        # Connect to the Pod and make sure it is valid.
        client = self._get_client(pod_id, context)
        if not client.has_api_extension("virtual-machines"):
            raise LXDPodError(
                "Please upgrade your LXD host to 3.19+ for virtual machine support."
            )

        self._ensure_project(client)

        # get MACs for host interfaces. "unknown" interfaces are considered too
        # to match ethernets in containers
        networks_state = [
            net.state()
            for net in client.networks.all()
            if net.type in ("unknown", "physical")
        ]
        mac_addresses = list(
            {state.hwaddr for state in networks_state if state.hwaddr}
        )

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
            mac_addresses=mac_addresses,
            capabilities=[
                Capabilities.COMPOSABLE,
                Capabilities.DYNAMIC_LOCAL_STORAGE,
                Capabilities.OVER_COMMIT,
                Capabilities.STORAGE_POOLS,
            ],
        )

        # Check that we have at least one storage pool.
        # If not, user should be warned that they need to create one.
        storage_pools = client.storage_pools.all()
        if not storage_pools:
            raise LXDPodError(
                "No storage pools exists.  Please create a storage pool in LXD."
            )

        # Discover Storage Pools.
        pools = []
        local_storage = 0
        for storage_pool in storage_pools:
            discovered_storage_pool = self._get_discovered_pod_storage_pool(
                storage_pool
            )
            local_storage += discovered_storage_pool.storage
            pools.append(discovered_storage_pool)
        discovered_pod.storage_pools = pools
        discovered_pod.local_storage = local_storage

        host_cpu_speed = lxd_cpu_speed(client.resources)

        # Discover VMs.
        projects = [project.name for project in client.projects.all()]
        machines = []
        for project in projects:
            project_cli = self._get_client(pod_id, context, project=project)
            for virtual_machine in project_cli.virtual_machines.all():
                discovered_machine = self._get_discovered_machine(
                    project_cli,
                    virtual_machine,
                    storage_pools=discovered_pod.storage_pools,
                )
                discovered_machine.cpu_speed = host_cpu_speed
                machines.append(discovered_machine)
        discovered_pod.machines = machines

        # Return the DiscoveredPod.
        return discovered_pod

    @threadDeferred
    def get_commissioning_data(self, pod_id: int, context: dict):
        """Retreive commissioning data from LXD."""
        client = self._get_client(pod_id, context)
        resources = {
            # /1.0
            **client.host_info,
            # /1.0/resources
            "resources": client.resources,
            # /1.0/networks/<network>/state
            "networks": {
                net.name: dict(net.state()) for net in client.networks.all()
            },
        }
        return {LXD_OUTPUT_NAME: resources}

    @threadDeferred
    def compose(self, pod_id: int, context: dict, request: RequestedMachine):
        """Compose a virtual machine."""
        client = self._get_client(pod_id, context)
        # Check to see if there is a maas profile.  If not, use the default.
        try:
            profile = client.profiles.get("maas")
        except NotFound:
            # Fall back to default
            try:
                profile = client.profiles.get("default")
            except NotFound:
                raise LXDPodError(
                    f"Pod {pod_id}: MAAS needs LXD to have either a 'maas' "
                    "profile or a 'default' profile, defined."
                )
        storage_pools = client.storage_pools.all()
        default_storage_pool = context.get(
            "default_storage_pool_id", context.get("default_storage_pool")
        )

        definition = get_lxd_machine_definition(request, profile.name)
        definition["devices"] = {
            **self._get_machine_disks(
                request.block_devices, storage_pools, default_storage_pool
            ),
            **self._get_machine_nics(request.interfaces, profile),
        }

        # Create the machine.
        machine = client.virtual_machines.create(definition, wait=True)
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
        machine = self._get_machine(pod_id, context)
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

    def _get_machine_nics(self, requested_interfaces, profile):
        # Create and attach interfaces to the machine.
        # The reason we are doing this after the machine is created
        # is because pylxd doesn't have a way to override the devices
        # that are defined in the profile.  Since the profile is provided
        # by the user, we have no idea how many interfaces are defined.
        #
        # Currently, only the bridged type is supported with virtual machines.
        # https://lxd.readthedocs.io/en/latest/instances/#device-types
        nics = {}
        profile_devices = profile.devices
        device_names = []
        boot = True
        for interface in requested_interfaces:
            if interface.ifname is None:
                # No interface constraints sent so use the best
                # nic device from the profile's devices.
                device_name, device = self._get_best_nic_device_from_profile(
                    profile_devices
                )
                nics[device_name] = device
                if "boot.priority" not in device and boot:
                    nics[device_name]["boot.priority"] = "1"
                    boot = False
                device_names.append(device_name)
            else:
                nics[interface.ifname] = get_lxd_nic_device(interface)

                # Set to boot from the first nic
                if boot:
                    nics[interface.ifname]["boot.priority"] = "1"
                    boot = False
                device_names.append(interface.ifname)

        # Iterate over all of the profile's devices with type=nic and set to
        # type=none if it's not a NIC device.  This overrides the device
        # settings on the profile used by the machine.
        for name, config in profile_devices.items():
            if name not in device_names and config["type"] == "nic":
                nics[name] = {"type": "none"}

        return nics

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

        # when creating a project, by default don't enable per-project
        # resources. Enabling storage volumes requires setting up at least one
        # manually so that VMs can be created, and enabling profiles would
        # create a default profile with no root nor NIC devices.
        client.projects.create(
            name=client.project,
            description="Project managed by MAAS",
            config={
                "features.images": "false",
                "features.profiles": "false",
                "features.storage.volumes": "false",
            },
        )

    def _get_best_nic_device_from_profile(self, devices):
        """Return the nic name and device that is most likely to be
        on a MAAS DHCP enabled subnet.  This is used when no interface
        constraints are in the request."""
        nic_devices = {k: v for k, v in devices.items() if v["type"] == "nic"}

        # Check for boot.priority flag by sorting.
        # If the boot.priority flag is set, this will
        # most likely be an interface that is expected
        # to boot off the network.
        boot_priorities = sorted(
            {k: v for k, v in nic_devices.items() if "boot.priority" in v},
            key=lambda i: nic_devices[i]["boot.priority"],
            reverse=True,
        )

        if boot_priorities:
            return boot_priorities[0], nic_devices[boot_priorities[0]]

        # Since we couldn't find a nic device with boot.priority set
        # just choose the first nic device.
        device_name = list(nic_devices.keys())[0]
        return device_name, nic_devices[device_name]

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
            # When LXD creates a QEMU disk the serial is always
            # lxd_{device name}. The device_name is defined by
            # the LXD profile or when adding a device. This is
            # commonly "root" for the first disk. The model and
            # serial must be correctly defined here otherwise
            # MAAS will delete the disk created during composition
            # which results in losing the storage pool link. Without
            # the storage pool link MAAS can't determine how much
            # of the storage pool has been used.
            serial = f"lxd_{name}"
            source = device.get("source")
            if source:
                pool = client.storage_pools.get(device["pool"])
                volume = pool.volumes.get("custom", source)
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
                vid=int(device.get("vlan", get_vid_from_ifname(name))),
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
                block_devices.append(
                    _get_discovered_block_device(
                        name, device, requested_device=requested_device
                    )
                )
            elif device["type"] == "nic":
                interfaces.append(
                    _get_discovered_interface(name, device, not interfaces)
                )

        # LXD uses different suffixes to store memory so make
        # sure we convert to MiB, which is what MAAS uses.
        memory = expanded_config.get("limits.memory")
        if memory is not None:
            memory = convert_lxd_byte_suffixes(memory, divisor=1024 ** 2)
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
        )

    def _get_discovered_pod_storage_pool(self, storage_pool):
        """Get the Pod storage pool."""
        storage_pool_config = storage_pool.config
        # Sometimes the config is empty, use get() method on the dictionary in case.
        storage_pool_path = storage_pool_config.get("source")
        storage_pool_resources = storage_pool.resources.get()
        total_storage = storage_pool_resources.space["total"]

        return DiscoveredPodStoragePool(
            # No ID's with LXD so we are just using the name as the ID.
            id=storage_pool.name,
            name=storage_pool.name,
            path=storage_pool_path,
            type=storage_pool.driver,
            storage=total_storage,
        )

    @typed
    def _get_machine(self, pod_id: int, context: dict, fail: bool = True):
        """Retrieve LXD VM.

        If "fail" is False, return None instead of raising an exception.
        """
        client = self._get_client(pod_id, context)
        instance_name = context.get("instance_name")
        try:
            return client.virtual_machines.get(instance_name)
        except NotFound:
            if fail:
                raise LXDPodError(
                    f"Pod {pod_id}: LXD VM {instance_name} not found."
                )
            return None

    @typed
    def _get_client(
        self, pod_id: int, context: dict, project: Optional[str] = None
    ):
        """Connect PyLXD client."""
        if not project:
            project = context.get("project", "default")
        endpoint = self.get_url(context)
        try:
            client = Client(
                endpoint=endpoint,
                project=project,
                cert=get_maas_cert_tuple(),
                verify=False,
            )
            if not client.trusted:
                password = context.get("password")
                if password:
                    client.authenticate(password)
                else:
                    raise LXDPodError(
                        f"Pod {pod_id}: Certificate is not trusted and no password was given."
                    )
        except ClientConnectionFailed:
            raise LXDPodError(
                f"Pod {pod_id}: Failed to connect to the LXD REST API."
            )
        return client


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
