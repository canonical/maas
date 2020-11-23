# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD Pod Driver."""


from contextlib import suppress
import re
from urllib.parse import urlparse

from pylxd import Client
from pylxd.exceptions import ClientConnectionFailed, NotFound
from twisted.internet.defer import ensureDeferred, inlineCallbacks
from twisted.internet.threads import deferToThread

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
from provisioningserver.utils.twisted import asynchronous

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
    pinned_cores = request.pinned_cores
    if pinned_cores:
        if len(pinned_cores) == 1:
            limits_cpu = f"{pinned_cores[0]}-{pinned_cores[0]}"
        else:
            limits_cpu = ",".join(str(core) for core in pinned_cores)
    else:
        limits_cpu = str(request.cores)

    return {
        "name": request.hostname,
        "architecture": debian_to_kernel_architecture(request.architecture),
        "config": {
            "limits.cpu": limits_cpu,
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
    @inlineCallbacks
    def get_client(self, pod_id: str, context: dict):
        """Connect pylxd client."""
        endpoint = self.get_url(context)
        password = context.get("password")
        try:
            client = yield deferToThread(
                Client,
                endpoint=endpoint,
                cert=get_maas_cert_tuple(),
                verify=False,
            )
            if not client.trusted:
                if password:
                    yield deferToThread(client.authenticate, password)
                else:
                    raise LXDPodError(
                        f"Pod {pod_id}: Certificate is not trusted and no password was given."
                    )
        except ClientConnectionFailed:
            raise LXDPodError(
                f"Pod {pod_id}: Failed to connect to the LXD REST API."
            )
        return client

    @typed
    @inlineCallbacks
    def get_machine(self, pod_id: str, context: dict):
        """Retrieve LXD VM."""
        client = yield self.get_client(pod_id, context)
        instance_name = context.get("instance_name")
        try:
            machine = yield deferToThread(
                client.virtual_machines.get, instance_name
            )
        except NotFound:
            raise LXDPodError(
                f"Pod {pod_id}: LXD VM {instance_name} not found."
            )
        return machine

    async def get_discovered_machine(
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

        expanded_config = machine.expanded_config
        expanded_devices = machine.expanded_devices

        # Discover block devices.
        block_devices = []
        for idx, device in enumerate(expanded_devices):
            # Block device.
            # When request is provided map the tags from the request block
            # devices to the discovered block devices. This ensures that
            # composed machine has the requested tags on the block device.

            tags = []
            if (
                request is not None
                and expanded_devices[device]["type"] == "disk"
            ):
                tags = request.block_devices[0].tags

            device_info = expanded_devices[device]
            if device_info["type"] == "disk":
                # When LXD creates a QEMU disk the serial is always
                # lxd_{device name}. The device_name is defined by
                # the LXD profile or when adding a device. This is
                # commonly "root" for the first disk. The model and
                # serial must be correctly defined here otherwise
                # MAAS will delete the disk created during composition
                # which results in losing the storage pool link. Without
                # the storage pool link MAAS can't determine how much
                # of the storage pool has been used.
                serial = f"lxd_{device}"
                # Default disk size is 10GB.
                size = convert_lxd_byte_suffixes(
                    device_info.get("size", "10GB")
                )
                storage_pool = device_info.get("pool")
                block_devices.append(
                    DiscoveredMachineBlockDevice(
                        model="QEMU HARDDISK",
                        serial=serial,
                        id_path=f"/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_{serial}",
                        size=size,
                        tags=tags,
                        storage_pool=storage_pool,
                    )
                )

        # Discover interfaces.
        interfaces = []
        boot = True
        config_mac_address = {}
        for configuration in expanded_config:
            if configuration.endswith("hwaddr"):
                mac = expanded_config[configuration]
                name = configuration.split(".")[1]
                config_mac_address[name] = mac
        for name, device in expanded_devices.items():
            if device["type"] != "nic":
                continue
            device = expanded_devices[name]
            if "network" in device:
                # Try finding the nictype from the networks.
                # XXX: This should work for "bridge" networks,
                #      but will most likely produce weird results for the
                #      other types.
                network = await deferToThread(
                    client.networks.get, device["network"]
                )
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
                mac = config_mac_address.get(name)

            interfaces.append(
                DiscoveredMachineInterface(
                    mac_address=mac,
                    vid=int(device.get("vlan", get_vid_from_ifname(name))),
                    boot=boot,
                    attach_type=attach_type,
                    attach_name=attach_name,
                )
            )
            boot = False

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
            power_parameters={"instance_name": machine.name},
            tags=[],
            hugepages_backed=hugepages_backed,
            pinned_cores=pinned_cores,
            # LXD VMs use only UEFI.
            bios_boot_method="uefi",
        )

    def get_discovered_pod_storage_pool(self, storage_pool):
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
    @asynchronous
    @inlineCallbacks
    def power_on(self, pod_id: str, context: dict):
        """Power on LXD VM."""
        machine = yield self.get_machine(pod_id, context)
        if LXD_VM_POWER_STATE[machine.status_code] == "off":
            yield deferToThread(machine.start)

    @typed
    @asynchronous
    @inlineCallbacks
    def power_off(self, pod_id: str, context: dict):
        """Power off LXD VM."""
        machine = yield self.get_machine(pod_id, context)
        if LXD_VM_POWER_STATE[machine.status_code] == "on":
            yield deferToThread(machine.stop)

    @typed
    @asynchronous
    @inlineCallbacks
    def power_query(self, pod_id: str, context: dict):
        """Power query LXD VM."""
        machine = yield self.get_machine(pod_id, context)
        state = machine.status_code
        try:
            return LXD_VM_POWER_STATE[state]
        except KeyError:
            raise LXDPodError(
                f"Pod {pod_id}: Unknown power status code: {state}"
            )

    async def discover(self, pod_id, context):
        """Discover all Pod host resources."""
        # Connect to the Pod and make sure it is valid.
        client = await self.get_client(pod_id, context)
        if not client.has_api_extension("virtual-machines"):
            raise LXDPodError(
                "Please upgrade your LXD host to 3.19+ for virtual machine support."
            )
        resources = await deferToThread(lambda: client.resources)

        mac_addresses = []
        for card in resources["network"]["cards"]:
            for port in card["ports"]:
                mac_addresses.append(port["address"])

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
                    client.host_info["environment"]["kernel_architecture"]
                )
            ],
            name=client.host_info["environment"]["server_name"],
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
        storage_pools = await deferToThread(client.storage_pools.all)
        if not storage_pools:
            raise LXDPodError(
                "No storage pools exists.  Please create a storage pool in LXD."
            )

        # Discover Storage Pools.
        pools = []
        storage_pools = await deferToThread(client.storage_pools.all)
        local_storage = 0
        for storage_pool in storage_pools:
            discovered_storage_pool = self.get_discovered_pod_storage_pool(
                storage_pool
            )
            local_storage += discovered_storage_pool.storage
            pools.append(discovered_storage_pool)
        discovered_pod.storage_pools = pools
        discovered_pod.local_storage = local_storage

        # Discover VMs.
        machines = []
        virtual_machines = await deferToThread(client.virtual_machines.all)
        for virtual_machine in virtual_machines:
            discovered_machine = await self.get_discovered_machine(
                client,
                virtual_machine,
                storage_pools=discovered_pod.storage_pools,
            )
            discovered_machine.cpu_speed = lxd_cpu_speed(resources)
            machines.append(discovered_machine)
        discovered_pod.machines = machines

        # Return the DiscoveredPod.
        return discovered_pod

    @asynchronous
    def get_commissioning_data(self, pod_id, context):
        """Retreive commissioning data from LXD."""
        d = self.get_client(pod_id, context)
        # Replicate the LXD API in tree form, like machine-resources does.
        d.addCallback(
            lambda client: {
                # /1.0
                **client.host_info,
                # /1.0/resources
                "resources": client.resources,
                # TODO - Add networking information.
                # /1.0/networks
                # 'networks': {'eth0': {...}, 'eth1': {...}, 'bond0': {...}},
            }
        )
        d.addCallback(lambda resources: {LXD_OUTPUT_NAME: resources})
        return d

    def get_usable_storage_pool(
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
                    return storage_pool.name
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
                    return default_storage_pool.name
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
                return storage_pool.name
        raise PodInvalidResources(
            "Not enough storage space on any storage pools: %s"
            % (
                ", ".join(
                    [storage_pool.name for storage_pool in storage_pools]
                )
            )
        )

    @inlineCallbacks
    def compose(self, pod_id: str, context: dict, request: RequestedMachine):
        """Compose a virtual machine."""
        client = yield self.get_client(pod_id, context)
        # Check to see if there is a maas profile.  If not, use the default.
        try:
            profile = yield deferToThread(client.profiles.get, "maas")
        except NotFound:
            # Fall back to default
            try:
                profile = yield deferToThread(client.profiles.get, "default")
            except NotFound:
                raise LXDPodError(
                    f"Pod {pod_id}: MAAS needs LXD to have either a 'maas' "
                    "profile or a 'default' profile, defined."
                )
        resources = yield deferToThread(lambda: client.resources)

        definition = get_lxd_machine_definition(request, profile.name)

        # Add disk to the definition.
        # XXX: LXD VMs currently only support one virtual block device.
        # Loop will need to be modified once LXD has multiple virtual
        # block device support.
        devices = {}
        storage_pools = yield deferToThread(client.storage_pools.all)
        default_storage_pool = context.get(
            "default_storage_pool_id", context.get("default_storage_pool")
        )
        for idx, disk in enumerate(request.block_devices):
            usable_pool = self.get_usable_storage_pool(
                disk, storage_pools, default_storage_pool
            )
            devices["root"] = {
                "path": "/",
                "type": "disk",
                "pool": usable_pool,
                "size": str(disk.size),
                "boot.priority": "0",
            }

        # Create and attach interfaces to the machine.
        # The reason we are doing this after the machine is created
        # is because pylxd doesn't have a way to override the devices
        # that are defined in the profile.  Since the profile is provided
        # by the user, we have no idea how many interfaces are defined.
        #
        # Currently, only the bridged type is supported with virtual machines.
        # https://lxd.readthedocs.io/en/latest/instances/#device-types
        nic_devices = {}
        profile_devices = profile.devices
        device_names = []
        boot = True
        for interface in request.interfaces:
            if interface.ifname is None:
                # No interface constraints sent so use the best
                # nic device from the profile's devices.
                device_name, device = self.get_best_nic_device_from_profile(
                    profile_devices
                )
                nic_devices[device_name] = device
                if "boot.priority" not in device and boot:
                    nic_devices[device_name]["boot.priority"] = "1"
                    boot = False
                device_names.append(device_name)
            else:
                nic_devices[interface.ifname] = get_lxd_nic_device(interface)

                # Set to boot from the first nic
                if boot:
                    nic_devices[interface.ifname]["boot.priority"] = "1"
                    boot = False
                device_names.append(interface.ifname)

        # Iterate over all of the profile's devices with type=nic
        # and set to type=none if not nic_device.  This overrides
        # the device settings on the profile used by the machine.
        for dk, dv in profile_devices.items():
            if dk not in device_names and dv["type"] == "nic":
                nic_devices[dk] = {"type": "none"}

        # Merge the devices and attach the devices to the defintion.
        for k, v in nic_devices.items():
            devices[k] = v
        definition["devices"] = devices

        # Create the machine.
        machine = yield deferToThread(
            client.virtual_machines.create, definition, wait=True
        )
        # Pod hints are updated on the region after the machine
        # is composed.
        discovered_machine = yield ensureDeferred(
            self.get_discovered_machine(
                client, machine, storage_pools, request=request
            )
        )
        # Update the machine cpu speed.
        discovered_machine.cpu_speed = lxd_cpu_speed(resources)
        return discovered_machine, DiscoveredPodHints()

    def get_best_nic_device_from_profile(self, devices):
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

    @inlineCallbacks
    def decompose(self, pod_id, context):
        """Decompose a virtual machine."""
        client = yield self.get_client(pod_id, context)

        def sync_decompose(instance_name):
            machine = client.virtual_machines.get(instance_name)
            machine.stop(force=True, wait=True)
            machine.delete(wait=True)

        yield deferToThread(sync_decompose, context["instance_name"])
        # Hints are updated on the region for LXDPodDriver.
        return DiscoveredPodHints()


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


def _get_bool(value):
    """Convert the given LXD config value to a bool."""
    if not value:
        return False
    return value.lower() in ("true", "1")
