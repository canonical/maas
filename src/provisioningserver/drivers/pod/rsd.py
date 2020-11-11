# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rack Scale Design pod driver."""


from http import HTTPStatus
from io import BytesIO
import json
from os.path import join

from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import (
    Agent,
    FileBodyProducer,
    PartialDownloadError,
    readBody,
)

from provisioningserver.drivers import (
    make_ip_extractor,
    make_setting_field,
    SETTING_SCOPE,
)
from provisioningserver.drivers.pod import (
    BlockDeviceType,
    Capabilities,
    DiscoveredMachine,
    DiscoveredMachineBlockDevice,
    DiscoveredMachineInterface,
    DiscoveredPod,
    DiscoveredPodHints,
    PodActionError,
    PodDriverBase,
    PodFatalError,
)
from provisioningserver.drivers.power.redfish import (
    RedfishPowerDriverBase,
    WebClientContextFactory,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import PodInvalidResources
from provisioningserver.utils.twisted import asynchronous, pause

maaslog = get_maas_logger("drivers.pod.rsd")

RSD_POWER_CONTROL_ENDPOINT = b"redfish/v1/Nodes/%s/Actions/ComposedNode.Reset"

# RSD stores the architecture with a different
# label then MAAS. This maps RSD architecture to
# MAAS architecture.
RSD_ARCH = {"x86-64": "amd64/generic"}

# RSD system power states.
RSD_SYSTEM_POWER_STATE = {
    "On": "on",
    "Off": "off",
    "PoweringOn": "on",
    "PoweringOff": "on",
}


RSD_NODE_POWER_STATE = {"PoweredOn": "on", "PoweredOff": "off"}


class RSDPodDriver(RedfishPowerDriverBase, PodDriverBase):

    chassis = True  # Pods are always a chassis
    can_probe = False

    # RSDPodDriver inherits from RedfishPowerDriver.
    # Power parameters will need to be changed to reflect this.
    name = "rsd"
    description = "Rack Scale Design"
    settings = [
        make_setting_field("power_address", "Address", required=True),
        make_setting_field("power_user", "User", required=True),
        make_setting_field(
            "power_pass", "Password", field_type="password", required=True
        ),
        make_setting_field(
            "node_id", "Node ID", scope=SETTING_SCOPE.NODE, required=True
        ),
    ]
    ip_extractor = make_ip_extractor("power_address")

    def detect_missing_packages(self):
        # no required packages
        return []

    @asynchronous
    def redfish_request(self, method, uri, headers=None, bodyProducer=None):
        """Send the redfish request and return the response."""
        agent = Agent(reactor, contextFactory=WebClientContextFactory())
        d = agent.request(
            method, uri, headers=headers, bodyProducer=bodyProducer
        )

        def render_response(response):
            """Render the HTTPS response received."""

            def eb_catch_partial(failure):
                # Twisted is raising PartialDownloadError because the responses
                # do not contain a Content-Length header. Since every response
                # holds the whole body we just take the result.
                failure.trap(PartialDownloadError)
                if int(failure.value.status) == HTTPStatus.OK:
                    return failure.value.response
                else:
                    return failure

            def cb_json_decode(data):
                data = data.decode("utf-8")
                # Only decode non-empty response bodies.
                if data:
                    response = json.loads(data)
                    if "error" in response:
                        messages = response.get("error").get(
                            "@Message.ExtendedInfo"
                        )
                        message = "\n".join(
                            [message.get("Message") for message in messages]
                        )
                        raise PodActionError(message)
                    else:
                        return response

            def cb_attach_headers(data, headers):
                return data, headers

            d = readBody(response)
            d.addErrback(eb_catch_partial)
            d.addCallback(cb_json_decode)
            d.addCallback(cb_attach_headers, headers=response.headers)
            return d

        d.addCallback(render_response)
        return d

    @inlineCallbacks
    def list_resources(self, uri, headers):
        """Return the list of the resources for the given uri.

        This method is for a specific RSD uri that have a
        `Members` attribute with a list of members which populate the
        list.
        """
        resources, _ = yield self.redfish_request(b"GET", uri, headers)
        members = resources.get("Members")
        resource_ids = []
        for resource in members:
            resource_ids.append(
                resource["@odata.id"].lstrip("/").encode("utf-8")
            )
        return resource_ids

    @inlineCallbacks
    def scrape_logical_drives_and_targets(self, url, headers):
        """ Scrape the logical drive and targets data from storage services."""
        logical_drives = {}
        target_links = {}
        # Get list of all services in the pod.
        services_uri = join(url, b"redfish/v1/Services")
        services = yield self.list_resources(services_uri, headers)
        # Iterate over all services in the pod.
        for service in services:
            # Get list of all the logical volumes for this service.
            logical_volumes_uri = join(url, service, b"LogicalDrives")
            logical_volumes = yield self.list_resources(
                logical_volumes_uri, headers
            )
            for logical_volume in logical_volumes:
                lv_data, _ = yield self.redfish_request(
                    b"GET", join(url, logical_volume), headers
                )
                logical_drives[logical_volume] = lv_data
            # Get list of all the targets for this service.
            targets_uri = join(url, service, b"Targets")
            targets = yield self.list_resources(targets_uri, headers)
            for target in targets:
                target_data, _ = yield self.redfish_request(
                    b"GET", join(url, target), headers
                )
                target_links[target] = target_data
        return logical_drives, target_links

    @inlineCallbacks
    def scrape_remote_drives(self, url, headers):
        """Scrape remote drives (targets) from composed nodes."""
        targets = []
        nodes_uri = join(url, b"redfish/v1/Nodes")
        nodes = yield self.list_resources(nodes_uri, headers)
        for node in nodes:
            node_data, _ = yield self.redfish_request(
                b"GET", join(url, node), headers
            )
            remote_drives = node_data.get("Links", {}).get("RemoteDrives", [])
            for remote_drive in remote_drives:
                targets.append(remote_drive["@odata.id"])
        return set(targets)

    def calculate_remote_storage(self, remote_drives, logical_drives, targets):
        """Find and calculate the total, available, and master logical volume for each
        logical volume group in the pod.
        """
        # Find LVGs and LVs out of all logical drives.
        lvgs = {}
        lvs = {}
        for lv, lv_data in logical_drives.items():
            if lv_data["Mode"] == "LVG":
                lvgs[lv] = lv_data
            elif lv_data["Mode"] == "LV":
                lvs[lv] = lv_data

        # For each LVG, calculate total amount of usable space,
        # total amount of available space, and find the master volume to clone.
        # The master volume is the LV with the lowest ID.
        remote_storage = {}
        for lvg, lvg_data in lvgs.items():
            total = 0
            available = 0
            master_id = 0
            master_size = 0
            master_path = None

            # Find size of LVG and get LVs for this LVG.
            lvg_capacity = lvg_data["CapacityGiB"]
            lvg_lvs = lvg_data.get("Links", {}).get("LogicalDrives", [])

            # Find total capacity, capacity with no targets, and capacity
            # with unused targets for all LVs in this LVG.
            lvs_total_capacity = 0
            lvs_capacity_no_targets = 0
            lvs_capacity_unused = 0
            for lvg_lv in lvg_lvs:
                lv_link = lvg_lv["@odata.id"].lstrip("/").encode("utf-8")
                # Extract JSON data from stored LV.
                if lv_link in lvs:
                    lv_info = lvs[lv_link]
                else:
                    # Continue on to next lv.
                    continue
                lv_capacity = lv_info["CapacityGiB"]
                lvs_total_capacity += lv_capacity
                lv_targets = lv_info.get("Links", {}).get("Targets", [])
                if not lv_targets:
                    lvs_capacity_no_targets += lv_capacity
                else:
                    lv_target_links = {lv["@odata.id"] for lv in lv_targets}
                    # If all of the targets are unused, we count it as unused.
                    if not (lv_target_links & remote_drives):
                        lvs_capacity_unused += lv_capacity
                new_master_id = int(lv_info["Id"])
                if master_path is None or master_id > new_master_id:
                    master_path = b"/" + lv_link
                    master_size = lv_capacity
                    master_id = new_master_id

            total = (
                lvg_capacity - lvs_capacity_no_targets - lvs_capacity_unused
            )
            total *= 1024 ** 3
            available = (lvg_capacity - lvs_total_capacity) * (1024 ** 3)
            remote_storage[lvg] = {
                "total": total,
                "available": available,
                "master": {"path": master_path, "size": master_size},
            }
        return remote_storage

    def calculate_pod_remote_storage(
        self, remote_drives, logical_drives, targets
    ):
        """Calculate the total sum of logical volume group capacities in the pod
        and retrieve the largest LV for the hints.
        """
        remote_storage = self.calculate_remote_storage(
            remote_drives, logical_drives, targets
        )

        total_capacity = 0
        for lvg, rs_data in remote_storage.items():
            total_capacity += rs_data["total"]

        hint_capacity = 0
        for lv, lv_data in logical_drives.items():
            if lv_data["Mode"] == "LV":
                if lv_data["CapacityGiB"] > hint_capacity:
                    hint_capacity = lv_data["CapacityGiB"]
        hint_capacity *= 1024 ** 3

        return total_capacity, hint_capacity

    @inlineCallbacks
    def get_pod_memory_resources(self, url, headers, system):
        """Get all the memory resources for the given system."""
        system_memory = []
        # Get list of all memories for this specific system.
        memories_uri = join(url, system, b"Memory")
        memories = yield self.list_resources(memories_uri, headers)
        # Iterate over all the memories for this specific system.
        for memory in memories:
            memory_data, _ = yield self.redfish_request(
                b"GET", join(url, memory), headers
            )
            system_memory.append(memory_data.get("CapacityMiB"))
        return system_memory

    @inlineCallbacks
    def get_pod_processor_resources(self, url, headers, system):
        """Get all processor resources for the given system."""
        cores = []
        cpu_speeds = []
        arch = ""
        # Get list of all processors for this specific system.
        processors_uri = join(url, system, b"Processors")
        processors = yield self.list_resources(processors_uri, headers)
        # Iterate over all processors for this specific system.
        for processor in processors:
            processor_data, _ = yield self.redfish_request(
                b"GET", join(url, processor), headers
            )
            # Using 'TotalThreads' instead of 'TotalCores'
            # as this is what MAAS finds when commissioning.
            cores.append(processor_data.get("TotalThreads"))
            cpu_speeds.append(processor_data.get("MaxSpeedMHz"))
            # Only choose first processor architecture found.
            if arch == "":
                arch = processor_data.get("InstructionSet")
        return cores, cpu_speeds, arch

    @inlineCallbacks
    def get_pod_storage_resources(self, url, headers, system):
        """Get all local storage resources for the given system."""
        storages = []
        # Get list of all adapters for this specific system.
        adapters_uri = join(url, system, b"Adapters")
        adapters = yield self.list_resources(adapters_uri, headers)
        # Iterate over all the adapters for this specific system.
        for adapter in adapters:
            # Get list of all the devices for this specific adapter.
            devices_uri = join(url, adapter, b"Devices")
            devices = yield self.list_resources(devices_uri, headers)
            # Iterate over all the devices for this specific adapter.
            for device in devices:
                device_data, _ = yield self.redfish_request(
                    b"GET", join(url, device), headers
                )
                storages.append(device_data.get("CapacityGiB"))
        return storages

    @inlineCallbacks
    def get_pod_resources(self, url, headers):
        """Get the pod resources."""
        discovered_pod = DiscoveredPod(
            architectures=[],
            cores=0,
            cpu_speed=0,
            memory=0,
            local_storage=0,
            local_disks=0,
            capabilities=[
                Capabilities.COMPOSABLE,
                Capabilities.FIXED_LOCAL_STORAGE,
            ],
            hints=DiscoveredPodHints(
                cores=0, cpu_speed=0, memory=0, local_storage=0, local_disks=0
            ),
        )
        # Save list of all cpu_speeds that we will use later
        # in our pod hints calculations.
        discovered_pod.cpu_speeds = []
        # Retrieve pod max cpu speed, total cores, total memory,
        # and total local storage.
        # Get list of all systems in the pod.
        systems_uri = join(url, b"redfish/v1/Systems")
        systems = yield self.list_resources(systems_uri, headers)
        # Iterate over all systems in the pod.
        for system in systems:
            memories = yield self.get_pod_memory_resources(
                url, headers, system
            )
            # Get processor data for this specific system.
            cores, cpu_speeds, arch = yield self.get_pod_processor_resources(
                url, headers, system
            )
            # Get storage data for this specific system.
            storages = yield self.get_pod_storage_resources(
                url, headers, system
            )

            if (
                None in (memories + cores + cpu_speeds + storages)
                or arch is None
            ):
                # Skip this system's data as it is not available.
                maaslog.warning(
                    "RSD system ID '%s' is missing required information."
                    "  System will not be included in discovered resources."
                    % system.decode("utf-8").rsplit("/")[-1]
                )
                continue
            else:
                arch = RSD_ARCH.get(arch, arch)
                if arch not in discovered_pod.architectures:
                    discovered_pod.architectures.append(arch)
                discovered_pod.memory += sum(memories)
                discovered_pod.cores += sum(cores)
                discovered_pod.cpu_speeds.extend(cpu_speeds)
                # GiB to Bytes.
                discovered_pod.local_storage += sum(storages) * (1024 ** 3)
                discovered_pod.local_disks += len(storages)

        # Set cpu_speed to max of all found cpu_speeds.
        if len(discovered_pod.cpu_speeds):
            discovered_pod.cpu_speed = max(discovered_pod.cpu_speeds)
        return discovered_pod

    @inlineCallbacks
    def get_pod_machine_memories(
        self, node_data, url, headers, discovered_machine
    ):
        """Get pod machine memories."""
        memories = node_data.get("Links", {}).get("Memory", [])
        for memory in memories:
            memory_data, _ = yield self.redfish_request(
                b"GET",
                join(url, memory["@odata.id"].lstrip("/").encode("utf-8")),
                headers,
            )
            discovered_machine.memory += memory_data["CapacityMiB"]

    @inlineCallbacks
    def get_pod_machine_processors(
        self, node_data, url, headers, discovered_machine
    ):
        """Get pod machine processors."""
        processors = node_data.get("Links", {}).get("Processors", [])
        for processor in processors:
            processor_data, _ = yield self.redfish_request(
                b"GET",
                join(url, processor["@odata.id"].lstrip("/").encode("utf-8")),
                headers,
            )
            # Using 'TotalThreads' instead of 'TotalCores'
            # as this is what MAAS finds when commissioning.
            discovered_machine.cores += processor_data["TotalThreads"]
            discovered_machine.cpu_speeds.append(processor_data["MaxSpeedMHz"])
            # Set architecture to first processor
            # architecture type found.
            if not discovered_machine.architecture:
                arch = processor_data["InstructionSet"]
                discovered_machine.architecture = RSD_ARCH.get(arch, arch)

    @inlineCallbacks
    def get_pod_machine_local_storages(
        self, node_data, url, headers, discovered_machine, request=None
    ):
        """Get pod machine local strorages."""
        local_drives = node_data.get("Links", {}).get("LocalDrives", [])
        for local_drive in local_drives:
            local_drive_endpoint = local_drive["@odata.id"]
            discovered_machine_block_device = DiscoveredMachineBlockDevice(
                model="", serial="", size=0
            )
            drive_data, _ = yield self.redfish_request(
                b"GET",
                join(url, local_drive_endpoint.lstrip("/").encode("utf-8")),
                headers,
            )
            discovered_machine_block_device.model = drive_data["Model"]
            discovered_machine_block_device.serial = drive_data["SerialNumber"]
            discovered_machine_block_device.size = float(
                drive_data["CapacityGiB"]
            ) * (1024 ** 3)

            # Map the tags from the request block devices to the discovered
            # block devices. This ensures that the composed machine has the
            # requested tags on the block device.
            if request is not None:
                # Iterate over all the request's block devices and pick
                # device that has 'local' flag set with smallest adequate size.
                chosen_block_device = None
                smallest_size = discovered_machine_block_device.size
                for block_device in request.block_devices:
                    if (
                        "local" in block_device.tags
                        and smallest_size >= block_device.size
                    ):
                        smallest_size = block_device.size
                        chosen_block_device = block_device
                if chosen_block_device is not None:
                    discovered_machine_block_device.tags = (
                        chosen_block_device.tags
                    )
                    # Delete this from the request's block devices as it
                    # is no longer needed.
                    request.block_devices.remove(chosen_block_device)
                else:
                    # Log the fact that we did not find a chosen block device
                    # to set the tags.  If the RSD is performing the way it
                    # should, the user should not be seeing this as the
                    # allocation process for composition should have failed.
                    # Warn the user of this.
                    maaslog.warning(
                        "Requested disk size is larger than %d GiB, which "
                        "drive '%r' contains.  RSD allocation should have "
                        "failed.  Please report this to your RSD Pod "
                        "administrator."
                        % (smallest_size / (1024 ** 3), local_drive_endpoint)
                    )

            if "local" not in discovered_machine_block_device.tags:
                discovered_machine_block_device.tags.append("local")
            if (
                drive_data["Type"] == "SSD"
                and "ssd" not in discovered_machine_block_device.tags
            ):
                discovered_machine_block_device.tags.append("ssd")
            discovered_machine.block_devices.append(
                discovered_machine_block_device
            )

    def get_pod_machine_remote_storages(
        self,
        node_data,
        url,
        headers,
        remote_drives,
        logical_drives,
        targets,
        discovered_machine,
        request=None,
    ):
        """Get pod machine remote storages."""
        node_remote_drives = node_data.get("Links", {}).get("RemoteDrives", [])
        remote_drives_to_delete = []
        logical_drives_to_delete = []
        for node_remote_drive in node_remote_drives:
            target_data = targets[
                node_remote_drive["@odata.id"].lstrip("/").encode("utf-8")
            ]
            initiator = target_data.get("Initiator")[0]
            initiator_iqn = initiator.get("iSCSI", {}).get("InitiatorIQN")
            if initiator_iqn:
                # Since InitiatorIQN is not an empty string we will not be
                # including this storage into MAAS.
                # Remove the remote drive, target, and logical drives
                # associated with this target.
                for lv, lv_data in logical_drives.items():
                    lv_targets = lv_data.get("Links", {}).get("Targets", [])
                    for lv_target in lv_targets:
                        if (
                            node_remote_drive["@odata.id"]
                            == lv_target["@odata.id"]
                        ):
                            remote_drives_to_delete.append(
                                node_remote_drive["@odata.id"]
                            )
                            logical_drives_to_delete.append(lv)
                continue

            discovered_machine_block_device = DiscoveredMachineBlockDevice(
                model=None, serial=None, size=0, type=BlockDeviceType.ISCSI
            )
            addresses = target_data.get("Addresses")[0]
            host = addresses.get("iSCSI", {}).get("TargetPortalIP")
            proto = "6"  # curtin currently only supports TCP.
            port = str(addresses.get("iSCSI", {}).get("TargetPortalPort"))
            luns = addresses.get("iSCSI", {}).get("TargetLUN", [])
            if luns:
                lun = str(luns[0]["LUN"])
            else:
                # Set LUN to 0 if not available.
                lun = "0"
            target_name = addresses.get("iSCSI", {}).get("TargetIQN")
            discovered_machine_block_device.iscsi_target = ":".join(
                [host, proto, port, lun, target_name]
            )
            # Loop through all the logical drives till we
            # find which one contains this remote drive.
            for lv, lv_data in logical_drives.items():
                lv_targets = lv_data.get("Links", {}).get("Targets", [])
                for lv_target in lv_targets:
                    if (
                        node_remote_drive["@odata.id"]
                        == lv_target["@odata.id"]
                    ):
                        discovered_machine_block_device.size = float(
                            lv_data["CapacityGiB"]
                        ) * (1024 ** 3)

            # Map the tags from the request block devices to the discovered
            # block devices. This ensures that the composed machine has the
            # requested tags on the block device.
            if request is not None:
                # Iterate over all the request's block devices to match on
                # target name to retrieve the tags.
                for block_device in request.block_devices:
                    bd_iscsi_target = getattr(
                        block_device, "iscsi_target", None
                    )
                    if bd_iscsi_target is not None:
                        if block_device.iscsi_target == target_name:
                            discovered_machine_block_device.tags = (
                                block_device.tags
                            )
                            # Delete this from the request's block
                            # devices as it is not longer needed.
                            request.block_devices.remove(block_device)

            if "iscsi" not in discovered_machine_block_device.tags:
                discovered_machine_block_device.tags.append("iscsi")
            discovered_machine.block_devices.append(
                discovered_machine_block_device
            )

        # Remove the remote drives, targests, and logical drives that
        # are no longer needed.  These will be used in later calculations
        # for the total usable iscsi remote storage.
        for remote_drive in set(remote_drives_to_delete):
            del targets[remote_drive.lstrip("/").encode("utf-8")]
            remote_drives.remove(remote_drive)
        for logical_drive in set(logical_drives_to_delete):
            del logical_drives[logical_drive]

    @inlineCallbacks
    def get_pod_machine_interfaces(
        self, node_data, url, headers, discovered_machine
    ):
        """Get pod machine interfaces."""
        interfaces = node_data.get("Links", {}).get("EthernetInterfaces", [])
        for interface in interfaces:
            discovered_machine_interface = DiscoveredMachineInterface(
                mac_address=""
            )
            interface_data, _ = yield self.redfish_request(
                b"GET",
                join(url, interface["@odata.id"].lstrip("/").encode("utf-8")),
                headers,
            )
            discovered_machine_interface.mac_address = interface_data[
                "MACAddress"
            ]
            nic_speed = interface_data["SpeedMbps"]
            if nic_speed is not None:
                if nic_speed < 1000:
                    discovered_machine_interface.tags = ["e%s" % nic_speed]
                elif nic_speed == 1000:
                    discovered_machine_interface.tags = ["1g", "e1000"]
                else:
                    # We know that the Mbps > 1000
                    discovered_machine_interface.tags = [
                        "%s" % (nic_speed / 1000)
                    ]
            # Oem can be empty sometimes, so let's check this.
            oem = interface_data.get("Links", {}).get("Oem")
            if oem:
                ports = oem.get("Intel_RackScale", {}).get("NeighborPort")
                if ports is not None:
                    for port in ports.values():
                        port = port.lstrip("/").encode("utf-8")
                        port_data, _ = yield self.redfish_request(
                            b"GET", join(url, port), headers
                        )
                        vlans = port_data.get("Links", {}).get("PrimaryVLAN")
                        if vlans is not None:
                            for vlan in vlans.values():
                                vlan = vlan.lstrip("/").encode("utf-8")
                                vlan_data, _ = yield self.redfish_request(
                                    b"GET", join(url, vlan), headers
                                )
                                discovered_machine_interface.vid = vlan_data[
                                    "VLANId"
                                ]
            else:
                # If no NeighborPort, this interface is on
                # the management network.
                discovered_machine_interface.boot = True

            discovered_machine.interfaces.append(discovered_machine_interface)

        boot_flags = [
            interface.boot for interface in discovered_machine.interfaces
        ]
        if len(boot_flags) > 0 and True not in boot_flags:
            # Just set first interface too boot.
            discovered_machine.interfaces[0].boot = True

    @inlineCallbacks
    def get_pod_machine(
        self,
        node,
        url,
        headers,
        remote_drives,
        logical_drives,
        targets,
        request=None,
    ):
        """Get pod composed machine.

        If required resources cannot be found, this
        composed machine will not be returned to the region.
        """
        discovered_machine = DiscoveredMachine(
            architecture="amd64/generic",
            cores=0,
            cpu_speed=0,
            memory=0,
            interfaces=[],
            block_devices=[],
            power_parameters={"node_id": node.decode("utf-8").rsplit("/")[-1]},
        )
        # Save list of all cpu_speeds being used by composed nodes
        # that we will use later in our pod hints calculations.
        discovered_machine.cpu_speeds = []
        node_data, _ = yield self.redfish_request(
            b"GET", join(url, node), headers
        )
        # Get hostname.
        discovered_machine.hostname = node_data["Name"]
        # Get power state.
        power_state = node_data["PowerState"]
        discovered_machine.power_state = RSD_SYSTEM_POWER_STATE.get(
            power_state
        )

        # Get memories.
        yield self.get_pod_machine_memories(
            node_data, url, headers, discovered_machine
        )
        # Get processors.
        yield self.get_pod_machine_processors(
            node_data, url, headers, discovered_machine
        )
        # Get local storages.
        yield self.get_pod_machine_local_storages(
            node_data, url, headers, discovered_machine, request
        )
        # Get remote storages.
        self.get_pod_machine_remote_storages(
            node_data,
            url,
            headers,
            remote_drives,
            logical_drives,
            targets,
            discovered_machine,
            request,
        )
        # Get interfaces.
        yield self.get_pod_machine_interfaces(
            node_data, url, headers, discovered_machine
        )
        # Set cpu_speed to max of all found cpu_speeds.
        if len(discovered_machine.cpu_speeds):
            discovered_machine.cpu_speed = max(discovered_machine.cpu_speeds)
        return discovered_machine

    @inlineCallbacks
    def get_pod_machines(
        self,
        url,
        headers,
        remote_drives,
        logical_drives,
        targets,
        request=None,
    ):
        """Get pod composed machines.

        If required resources cannot be found, these
        composed machines will not be included in the
        discovered machines returned to the region.
        """
        # Get list of all composed nodes in the pod.
        discovered_machines = []
        nodes_uri = join(url, b"redfish/v1/Nodes")
        nodes = yield self.list_resources(nodes_uri, headers)
        # Iterate over all composed nodes in the pod.
        for node in nodes:
            discovered_machine = yield self.get_pod_machine(
                node,
                url,
                headers,
                remote_drives,
                logical_drives,
                targets,
                request,
            )
            discovered_machines.append(discovered_machine)
        return discovered_machines

    def get_pod_hints(self, discovered_pod):
        """Gets the discovered pod hints."""
        discovered_pod_hints = DiscoveredPodHints(
            cores=0, cpu_speed=0, memory=0, local_storage=0, local_disks=0
        )
        used_cores = used_memory = used_storage = used_disks = 0
        for machine in discovered_pod.machines:
            for cpu_speed in machine.cpu_speeds:
                if cpu_speed in discovered_pod.cpu_speeds:
                    discovered_pod.cpu_speeds.remove(cpu_speed)
            used_cores += machine.cores
            used_memory += machine.memory
            for blk_dev in machine.block_devices:
                used_storage += blk_dev.size
                used_disks += 1

        if len(discovered_pod.cpu_speeds):
            discovered_pod_hints.cpu_speed = max(discovered_pod.cpu_speeds)
        discovered_pod_hints.cores = discovered_pod.cores - used_cores
        discovered_pod_hints.memory = discovered_pod.memory - used_memory
        discovered_pod_hints.local_storage = (
            discovered_pod.local_storage - used_storage
        )
        discovered_pod_hints.local_disks = (
            discovered_pod.local_disks - used_disks
        )
        return discovered_pod_hints

    @inlineCallbacks
    def discover(self, pod_id, context):
        """Discover all resources.

        Returns a defer to a DiscoveredPod object.
        """
        url = self.get_url(context)
        headers = self.make_auth_headers(**context)
        logical_drives, targets = yield self.scrape_logical_drives_and_targets(
            url, headers
        )
        remote_drives = yield self.scrape_remote_drives(url, headers)

        # Discover composed machines.
        pod_machines = yield self.get_pod_machines(
            url, headers, remote_drives, logical_drives, targets
        )

        # Discover pod resources.
        (
            pod_remote_storage,
            pod_hints_remote_storage,
        ) = self.calculate_pod_remote_storage(
            remote_drives, logical_drives, targets
        )
        discovered_pod = yield self.get_pod_resources(url, headers)

        # Add machines to pod.
        discovered_pod.machines = pod_machines

        # Discover pod remote storage resources.
        discovered_pod.capabilities.append(Capabilities.ISCSI_STORAGE)
        discovered_pod.iscsi_storage = pod_remote_storage

        # Discover pod hints.
        discovered_pod.hints = self.get_pod_hints(discovered_pod)
        discovered_pod.hints.iscsi_storage = pod_hints_remote_storage

        return discovered_pod

    def select_remote_master(self, remote_storage, size):
        """Select the remote master drive that has enough space."""
        for lvg, data in remote_storage.items():
            if data["master"] and data["available"] >= size:
                data["available"] -= size
                return data["master"]

    def set_drive_type(self, drive, block_device):
        """Set type of drive requested on `drive` based on the tags on
        `block_device`."""
        if "ssd" in block_device.tags:
            drive["Type"] = "SSD"
        elif "nvme" in block_device.tags:
            drive["Type"] = "NVMe"
        elif "hdd" in block_device.tags:
            drive["Type"] = "HDD"

    def convert_request_to_json_payload(
        self,
        processors,
        cores,
        request,
        remote_drives,
        logical_drives,
        targets,
    ):
        """Convert the RequestedMachine object to JSON."""
        # The below fields are for RSD allocation.
        # Most of these fields are nullable and could be used at
        # some future point by MAAS if set to None.
        # For complete list of fields, please see RSD documentation.
        processor = {
            "Model": None,
            "TotalCores": None,
            "AchievableSpeedMHz": None,
            "InstructionSet": None,
        }
        memory = {
            "CapacityMiB": None,
            # XXX: newell 2017-02-09 bug=1663074:
            # DimmDeviceType should be working but is currently
            # causing allocation errors in the RSD API.
            # "DimmDeviceType": None,
            "SpeedMHz": None,
            "DataWidthBits": None,
        }
        local_drive = {
            "CapacityGiB": None,
            "Type": None,
            "MinRPM": None,
            "SerialNumber": None,
            "Interface": None,
        }
        remote_drive = {
            "CapacityGiB": None,
            "iSCSIAddress": None,
            "Master": {"Type": "Snapshot", "Resource": None},
        }
        interface = {"SpeedMbps": None, "PrimaryVLAN": None}
        data = {
            "Name": request.hostname,
            "Processors": [],
            "Memory": [],
            "LocalDrives": [],
            "RemoteDrives": [],
            "EthernetInterfaces": [],
        }

        # Processors.
        for _ in range(processors):
            proc = processor.copy()
            proc["TotalCores"] = cores
            arch = request.architecture
            for key, val in RSD_ARCH.items():
                if val == arch:
                    proc["InstructionSet"] = key
            # cpu_speed is only optional field in request.
            cpu_speed = request.cpu_speed
            if cpu_speed is not None:
                proc["AchievableSpeedMHz"] = cpu_speed
            data["Processors"].append(proc)

        # Determine remote storage information if more than one block_device
        # is requested.
        remote_storage = None
        if len(request.block_devices) > 1:
            remote_storage = self.calculate_remote_storage(
                remote_drives, logical_drives, targets
            )

        # Block Devices.
        #
        # Tags are matched on the block devices to create different types
        # of requested storage for a block device.
        #     local: Locally attached disk (aka. LocalDrive).
        #     ssd: Locally attached SSD (aka. LocalDrive).
        #     hdd: Locally attached HDD (aka. LocalDrive).
        #     nvme: Locally attached NVMe (aka. LocalDrive).
        #     iscsi: Remotely attached disk over ISCSI (aka. RemoteTarget)
        #     (none): Remotely attached disk will be picked unless its the
        #             first disk. First disk is locally attached.
        block_devices = request.block_devices
        boot_disk = True
        for idx, block_device in enumerate(block_devices):
            if boot_disk:
                if "iscsi" in block_device.tags:
                    raise PodActionError(
                        "iSCSI is not supported as being a boot disk."
                    )
                else:
                    # Force 'local' into the tags if not present.
                    if "local" not in block_device.tags:
                        block_device.tags.append("local")
                    drive = local_drive.copy()
                    # Convert from bytes to GiB.
                    drive["CapacityGiB"] = block_device.size / (1024 ** 3)
                    self.set_drive_type(drive, block_device)
                    data["LocalDrives"].append(drive)
                boot_disk = False
            else:
                is_local = max(
                    tag in block_device.tags
                    for tag in ["local", "ssd", "nvme", "hdd"]
                )
                if is_local:
                    # Force the local tag if it wasn't provided.
                    if "local" not in block_device.tags:
                        block_device.tags.append("local")
                    drive = local_drive.copy()
                    # Convert from bytes to GiB.
                    drive["CapacityGiB"] = block_device.size / (1024 ** 3)
                    self.set_drive_type(drive, block_device)
                    data["LocalDrives"].append(drive)
                else:
                    # Force 'iscsi' into the tags if not present.
                    if "iscsi" not in block_device.tags:
                        block_device.tags.append("iscsi")
                    # Convert from bytes to GiB.
                    size = block_device.size / (1024 ** 3)

                    # Determine the remote master that can be used.
                    remote_master = self.select_remote_master(
                        remote_storage, size
                    )
                    if remote_master is None:
                        raise PodActionError(
                            "iSCSI remote drive cannot be created because "
                            "not enough space is available."
                        )
                    drive = remote_drive.copy()
                    drive["CapacityGiB"] = size
                    if remote_master["size"] > size:
                        drive["CapacityGiB"] = remote_master["size"]
                    drive["iSCSIAddress"] = "iqn.2010-08.io.maas:%s-%s" % (
                        request.hostname,
                        idx,
                    )
                    drive["Master"]["Resource"] = {
                        "@odata.id": remote_master["path"].decode("utf-8")
                    }
                    data["RemoteDrives"].append(drive)
                    # Save the iSCSIAddress on the RequestBlockDevice. This is
                    # used to map the DiscoveredMachineBlockDevice tags to
                    # the same tags used during the request.
                    block_device.iscsi_target = drive["iSCSIAddress"]

        # Interfaces.
        interfaces = request.interfaces
        for iface in interfaces:
            nic = interface.copy()
            data["EthernetInterfaces"].append(nic)

        # Memory.
        mem = memory.copy()
        mem["CapacityMiB"] = request.memory
        data["Memory"].append(mem)

        return json.dumps(data).encode("utf-8")

    @inlineCallbacks
    def compose(self, pod_id, context, request):
        """Compose machine."""
        url = self.get_url(context)
        headers = self.make_auth_headers(**context)
        endpoint = b"redfish/v1/Nodes/Actions/Allocate"
        logical_drives, targets = yield self.scrape_logical_drives_and_targets(
            url, headers
        )
        remote_drives = yield self.scrape_remote_drives(url, headers)
        # Create allocate payload.
        requested_cores = request.cores
        if requested_cores % 2 != 0:
            # Make cores an even number.
            requested_cores += 1
        # Divide by 2 since RSD TotalCores
        # is actually half of what MAAS reports.
        requested_cores //= 2

        # Find the correct procesors and cores combination from the pod.
        processors = 1
        cores = requested_cores
        response_headers = None
        while True:
            payload = self.convert_request_to_json_payload(
                processors,
                cores,
                request,
                remote_drives,
                logical_drives,
                targets,
            )
            try:
                _, response_headers = yield self.redfish_request(
                    b"POST",
                    join(url, endpoint),
                    headers,
                    FileBodyProducer(BytesIO(payload)),
                )
                # Break out of loop if allocation was successful.
                break
            except PartialDownloadError as error:
                response = json.loads(error.response.decode("utf-8"))
                if "error" in response:
                    messages = response.get("error").get(
                        "@Message.ExtendedInfo"
                    )
                    message = "\n".join(
                        [message.get("Message") for message in messages]
                    )
                    # Continue loop if allocation didn't work.
                    if "processors: 0" in message:
                        processors *= 2
                        cores //= 2
                        # Loop termination condition.
                        if cores == 0:
                            break
                        continue
                    else:
                        raise PodActionError(message)
            except Exception as exc:
                raise PodActionError("RSD compose error") from exc

        if response_headers is not None:
            location = response_headers.getRawHeaders("location")
            node_id = location[0].rsplit("/", 1)[-1]
            node_path = location[0].split("/", 3)[-1]

            # Assemble the node.
            yield self.assemble_node(url, node_id.encode("utf-8"), headers)
            # Set to PXE boot.
            yield self.set_pxe_boot(url, node_id.encode("utf-8"), headers)

            # Retrieve new node.
            # First, re-scrape the total lvs, used lvs, and targets.
            (
                logical_drives,
                targets,
            ) = yield self.scrape_logical_drives_and_targets(url, headers)
            remote_drives = yield self.scrape_remote_drives(url, headers)
            discovered_machine = yield self.get_pod_machine(
                node_path.encode("utf-8"),
                url,
                headers,
                remote_drives,
                logical_drives,
                targets,
                request,
            )

            # Retrieve pod resources.
            discovered_pod = yield self.get_pod_resources(url, headers)
            # Retrive pod hints.
            discovered_pod.hints = self.get_pod_hints(discovered_pod)

            return discovered_machine, discovered_pod.hints

        # Allocation did not succeed.
        raise PodInvalidResources(
            "Unable to allocate machine with requested resources."
        )

    @inlineCallbacks
    def delete_node(self, url, node_id, headers):
        """Delete node at node_id."""
        # Delete machine at node_id.
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        try:
            yield self.redfish_request(b"DELETE", join(url, endpoint), headers)
        except PartialDownloadError as error:
            # XXX newell 2017-02-27 bug=1667754:
            # Catch the 404 error when trying to decompose the
            # resource that has already been decomposed.
            if int(error.status) != HTTPStatus.NOT_FOUND:
                raise

    @inlineCallbacks
    def decompose(self, pod_id, context):
        """Decompose machine."""
        url = self.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = self.make_auth_headers(**context)
        yield self.delete_node(url, node_id, headers)

        # Retrieve pod resources.
        discovered_pod = yield self.get_pod_resources(url, headers)
        # Retrive pod hints.
        discovered_pod.hints = self.get_pod_hints(discovered_pod)

        return discovered_pod.hints

    @inlineCallbacks
    def get_composed_node_state(self, url, node_id, headers):
        """Return the `ComposedNodeState` of the composed machine."""
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        # Get endpoint data for node_id.
        node_data, _ = yield self.redfish_request(
            b"GET", join(url, endpoint), headers
        )
        return node_data.get("ComposedNodeState")

    @inlineCallbacks
    def assemble_node(self, url, node_id, headers):
        """Assemble composed machine with node_id."""
        node_state = yield self.get_composed_node_state(url, node_id, headers)
        if node_state in RSD_NODE_POWER_STATE:
            # Already assembled.
            return
        elif node_state == "Allocated":
            # Start assembling.
            endpoint = (
                b"redfish/v1/Nodes/%s/Actions/ComposedNode.Assemble" % node_id
            )
            yield self.redfish_request(b"POST", join(url, endpoint), headers)
        elif node_state == "Failed":
            # Broken system, delete allocated node.
            yield self.delete_node(url, node_id, headers)
            raise PodFatalError(
                "Composed machine at node ID %s has a ComposedNodeState"
                " of Failed." % node_id
            )

        # Assembling was started. Loop over until the state
        # changes from `Assembling`.
        node_state = yield self.get_composed_node_state(url, node_id, headers)
        while node_state == "Assembling":
            # Wait 2 seconds before getting updated state.
            yield pause(2)
            node_state = yield self.get_composed_node_state(
                url, node_id, headers
            )
        # Check one last time if the state has became `Failed`.

        if node_state == "Failed":
            # Broken system, delete allocated node.
            yield self.delete_node(url, node_id, headers)
            raise PodFatalError(
                "Composed machine at node ID %s has a ComposedNodeState"
                " of Failed." % node_id
            )

    @inlineCallbacks
    def set_pxe_boot(self, url, node_id, headers):
        """Set the composed machine with node_id to PXE boot."""
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        payload = FileBodyProducer(
            BytesIO(
                json.dumps(
                    {
                        "Boot": {
                            "BootSourceOverrideEnabled": "Once",
                            "BootSourceOverrideTarget": "Pxe",
                        }
                    }
                ).encode("utf-8")
            )
        )
        yield self.redfish_request(
            b"PATCH", join(url, endpoint), headers, payload
        )

    @inlineCallbacks
    def power(self, power_change, url, node_id, headers):
        endpoint = RSD_POWER_CONTROL_ENDPOINT % node_id
        payload = FileBodyProducer(
            BytesIO(
                json.dumps({"ResetType": "%s" % power_change}).encode("utf-8")
            )
        )
        yield self.redfish_request(
            b"POST", join(url, endpoint), headers, payload
        )

    @asynchronous
    @inlineCallbacks
    def power_on(self, system_id, context):
        """Power on composed machine."""
        url = self.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = self.make_auth_headers(**context)
        power_state = yield self.power_query(system_id, context)
        # Power off the machine if currently on.
        if power_state == "on":
            yield self.power("ForceOff", url, node_id, headers)
        # Set to PXE boot.
        yield self.set_pxe_boot(url, node_id, headers)
        # Power on the machine.
        yield self.power("On", url, node_id, headers)

    @asynchronous
    @inlineCallbacks
    def power_off(self, system_id, context):
        """Power off composed machine."""
        url = self.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = self.make_auth_headers(**context)
        # Set to PXE boot.
        yield self.set_pxe_boot(url, node_id, headers)
        # Power off the machine.
        yield self.power("ForceOff", url, node_id, headers)

    @asynchronous
    @inlineCallbacks
    def power_query(self, system_id, context):
        """Power query composed machine."""
        url = self.get_url(context)
        node_id = context.get("node_id").encode("utf-8")
        headers = self.make_auth_headers(**context)
        # Make sure the node is assembled for power
        # querying to work.
        yield self.assemble_node(url, node_id, headers)
        # We are now assembled, return the power state.
        node_state = yield self.get_composed_node_state(url, node_id, headers)
        if node_state in RSD_NODE_POWER_STATE:
            endpoint = b"redfish/v1/Nodes/%s" % node_id
            # Get endpoint data for node_id.
            node_data, _ = yield self.redfish_request(
                b"GET", join(url, endpoint), headers
            )
            power_state = node_data.get("PowerState")
            return RSD_SYSTEM_POWER_STATE.get(power_state)
        else:
            raise PodActionError("Unknown power state: %s" % node_state)
