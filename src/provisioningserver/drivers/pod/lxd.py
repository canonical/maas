# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""LXD Pod Driver."""

__all__ = []

from urllib.parse import urlparse

from pylxd import Client
from pylxd.exceptions import ClientConnectionFailed, NotFound
from twisted.internet.defer import inlineCallbacks
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
    DiscoveredPodStoragePool,
    PodDriver,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.maas_certificates import (
    MAAS_CERTIFICATE,
    MAAS_PRIVATE_KEY,
)
from provisioningserver.refresh.node_info_scripts import LXD_OUTPUT_NAME
from provisioningserver.utils import kernel_to_debian_architecture, typed
from provisioningserver.utils.ipaddr import get_vid_from_ifname
from provisioningserver.utils.twisted import asynchronous

maaslog = get_maas_logger("drivers.pod.lxd")

# LXD status codes
LXD_VM_POWER_STATE = {101: "on", 102: "off", 103: "on", 110: "off"}

# LXD vm disk path
LXD_VM_ID_PATH = "/dev/disk/by-id/scsi-0QEMU_QEMU_HARDDISK_lxd_"


class LXDPodError(Exception):
    """Failure communicating to LXD. """


class LXDPodDriver(PodDriver):

    name = "lxd"
    chassis = True
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
                cert=(MAAS_CERTIFICATE, MAAS_PRIVATE_KEY),
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

    def get_discovered_machine(
        self, machine, storage_pools, request=None, cpu_speed=0
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
            if request is not None:
                tags = request.block_devices[idx].tags

            device_info = expanded_devices[device]
            if device_info["type"] == "disk":
                # Default disk size is 10GB.
                size = device_info.get("size", 10 * 1000 ** 3)
                pool = device_info.get("pool")
                block_devices.append(
                    DiscoveredMachineBlockDevice(
                        model=None,
                        serial=None,
                        id_path=LXD_VM_ID_PATH + device,
                        size=size,
                        tags=tags,
                        storage_pool=pool,
                    )
                )

        # Discover interfaces.
        interfaces = []
        boot = True
        for configuration in expanded_config:
            if configuration.endswith("hwaddr"):
                mac = expanded_config[configuration]
                name = configuration.split(".")[1]
                nictype = expanded_devices[name]["nictype"]
                interfaces.append(
                    DiscoveredMachineInterface(
                        mac_address=mac,
                        vid=get_vid_from_ifname(name),
                        boot=boot,
                        attach_type=nictype,
                        attach_name=name,
                    )
                )
                boot = False

        return DiscoveredMachine(
            hostname=machine.name,
            architecture=kernel_to_debian_architecture(machine.architecture),
            # 1 core and 1GiB of memory (we need it in MiB) is default for
            # LXD if not specified.
            cores=int(expanded_config.get("limits.cpu", 1)),
            memory=int(expanded_config.get("limits.memory", 1024)),
            cpu_speed=cpu_speed,
            interfaces=interfaces,
            block_devices=block_devices,
            power_state=power_state,
            power_parameters={"instance_name": machine.name},
            tags=[],
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

    @inlineCallbacks
    def discover(self, pod_id, context):
        """Discover all Pod host resources."""
        # Connect to the Pod and make sure it is valid.
        client = yield self.get_client(pod_id, context)
        if not client.has_api_extension("virtual-machines"):
            raise LXDPodError(
                "Please upgrade your LXD host to 3.19+ for virtual machine support."
            )
        resources = yield deferToThread(lambda: client.resources)

        mac_addresses = []
        for card in resources["network"]["cards"]:
            for port in card["ports"]:
                mac_addresses.append(port["address"])

        # After the region creates the Pod object it will sync LXD commissioning
        # data for all hardware information.
        discovered_pod = DiscoveredPod(
            architectures=[
                kernel_to_debian_architecture(arch)
                for arch in client.host_info["environment"]["architectures"]
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

        # Check that we have at least one storage pool.  If not, create it.
        pools = yield deferToThread(client.storage_pools.all)
        if not len(pools):
            yield deferToThread(
                client.storage_pools.create, {"name": "maas", "driver": "dir"}
            )

        # Discover Storage Pools.
        pools = []
        storage_pools = yield deferToThread(client.storage_pools.all)
        for storage_pool in storage_pools:
            discovered_storage_pool = self.get_discovered_pod_storage_pool(
                storage_pool
            )
            pools.append(discovered_storage_pool)
        discovered_pod.storage_pools = pools

        # Discover VMs.
        machines = []
        virtual_machines = yield deferToThread(client.virtual_machines.all)
        for virtual_machine in virtual_machines:
            discovered_machine = self.get_discovered_machine(
                virtual_machine,
                storage_pools=discovered_pod.storage_pools,
                cpu_speed=discovered_pod.cpu_speed,
            )
            machines.append(discovered_machine)
        discovered_pod.machines = machines

        # Return the DiscoveredPod.
        return discovered_pod

    @inlineCallbacks
    def compose(self, pod_id, context, request):
        """Compose a virtual machine."""
        # abstract method, will update in subsequent branch.
        pass

    @inlineCallbacks
    def decompose(self, pod_id, context):
        """Decompose a virtual machine machine."""
        # abstract method, will update in subsequent branch.
        pass

    @asynchronous
    def get_commissioning_data(self, pod_id, context):
        """Retreive commissioning data from LXD."""
        d = self.get_client(pod_id, context)
        d.addCallback(lambda client: client.resources)
        d.addCallback(lambda resources: {LXD_OUTPUT_NAME: resources})
        return d
