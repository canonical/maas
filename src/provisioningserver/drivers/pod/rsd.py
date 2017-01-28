# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Rack Scale Design pod driver."""

__all__ = [
    'RSDPodDriver',
    ]

from base64 import b64encode
from http import HTTPStatus
from io import BytesIO
import json
from os.path import join

from provisioningserver.drivers import (
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
    PodActionError,
    PodDriver,
    PodFatalError,
)
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.twisted import asynchronous
from twisted.internet import reactor
from twisted.internet._sslverify import (
    ClientTLSOptions,
    OpenSSLCertificateOptions,
)
from twisted.internet.defer import inlineCallbacks
from twisted.web.client import (
    Agent,
    BrowserLikePolicyForHTTPS,
    FileBodyProducer,
    PartialDownloadError,
    readBody,
)
from twisted.web.http_headers import Headers


maaslog = get_maas_logger("drivers.pod.rsd")

# RSD stores the architecture with a different
# label then MAAS. This maps RSD architecture to
# MAAS architecture.
ARCH_FIX = {
    'x86_64': "amd64/generic",
    'x86': "amd64/generic",
    }

# RSD system power states.
RSD_SYSTEM_POWER_STATE = {
    'On': "on",
    'Off': "off",
    'PoweringOn': "on",
    'PoweringOff': "on",
    }


RSD_NODE_POWER_STATE = {
    'PoweredOn': "on",
    'PoweredOff': "off"
    }


RSD_RESOURCE_NOT_FOUND = (
    "Required RSD resource not available.  "
    "Unable to retrieve '%s' for endpoint: %s"
)


class RSDPodDriverError(Exception):
    """RSD Pod Driver error."""


class WebClientContextFactory(BrowserLikePolicyForHTTPS):

    def creatorForNetloc(self, hostname, port):
        opts = ClientTLSOptions(
            hostname.decode("ascii"),
            OpenSSLCertificateOptions(verify=False).getContext())
        # This forces Twisted to not validate the hostname of the certificate.
        opts._ctx.set_info_callback(lambda *args: None)
        return opts


class RSDPodDriver(PodDriver):

    name = 'rsd'
    description = "Rack Scale Design"
    settings = [
        make_setting_field(
            'power_address', "Pod address", required=True),
        make_setting_field('power_user', "Pod user", required=True),
        make_setting_field(
            'power_pass', "Pod password",
            field_type='password', required=True),
        make_setting_field(
            'node_id', "Node ID",
            scope=SETTING_SCOPE.NODE, required=True),
    ]
    ip_extractor = make_ip_extractor('power_address')

    def detect_missing_packages(self):
        # no required packages
        return []

    def get_url(self, context):
        """Return url for the pod."""
        url = context.get('power_address')
        if "https" not in url and "http" not in url:
            # Prepend https
            url = join("https://", url)
        return url.encode('utf-8')

    def make_auth_headers(self, power_user, power_pass, **kwargs):
        """Return authentication headers."""
        creds = "%s:%s" % (power_user, power_pass)
        authorization = b64encode(creds.encode('utf-8'))
        return Headers(
            {
                b"User-Agent": [b"MAAS"],
                b"Authorization": [b"Basic " + authorization],
                b"Content-Type": [b"application/json; charset=utf-8"],
            }
        )

    @asynchronous
    def redfish_request(self, method, uri, headers=None, bodyProducer=None):
        """Send the redfish request and return the response."""
        agent = Agent(reactor, contextFactory=WebClientContextFactory())
        d = agent.request(
            method, uri, headers=headers, bodyProducer=bodyProducer)

        def render_response(response):
            """Render the HTTPS response received."""

            def eb_catch_partial(failure):
                # Twisted is raising PartialDownloadError because the responses
                # do not contains a Content-Length header. Since every response
                # holds the whole body we just take the result.
                failure.trap(PartialDownloadError)
                if int(failure.value.status) == HTTPStatus.OK:
                    return failure.value.response
                else:
                    return failure

            def cb_json_decode(data):
                data = data.decode('utf-8')
                # Only decode non-empty responses.
                if data:
                    response = json.loads(data)
                    if "error" in response:
                        messages = response.get(
                            'error').get('@Message.ExtendedInfo')
                        message = "\n".join([
                            message.get('Message') for message in messages
                        ])
                        raise RSDPodDriverError(message)
                    else:
                        return response

            d = readBody(response)
            d.addErrback(eb_catch_partial)
            d.addCallback(cb_json_decode)
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
        resources = yield self.redfish_request(b"GET", uri, headers)
        members = resources.get('Members')
        resource_ids = []
        for resource in members:
            resource_ids.append(
                resource['@odata.id'].lstrip('/').encode('utf-8'))
        return resource_ids

    @inlineCallbacks
    def get_pod_memory_resources(self, url, headers, system):
        """Get all the memory resources for the given system."""
        system_memory = []
        # Get list of all memories for this specific system.
        memories_uri = join(url, system, b"Memory")
        memories = yield self.list_resources(memories_uri, headers)
        # Iterate over all the memories for this specific system.
        for memory in memories:
            memory_data = yield self.redfish_request(
                b"GET", join(url, memory), headers)
            system_memory.append(memory_data.get('CapacityMiB'))
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
            processor_data = yield self.redfish_request(
                b"GET", join(url, processor), headers)
            # Using 'TotalThreads' instead of 'TotalCores'
            # as this is what MAAS finds when commissioning.
            cores.append(processor_data.get('TotalThreads'))
            cpu_speeds.append(processor_data.get('MaxSpeedMHz'))
            # Only choose first processor architecture found.
            if arch == "":
                arch = processor_data.get('ProcessorArchitecture')
        return cores, cpu_speeds, arch

    @inlineCallbacks
    def get_pod_storage_resources(self, url, headers, system):
        """Get all local storage resources for the given system."""
        storages = []
        # Get list of all adapters for this specific system.
        adapters_uri = join(url, system, b"Adapters")
        adapters = yield self.list_resources(
            adapters_uri, headers)
        # Iterate over all the adapters for this specific system.
        for adapter in adapters:
            # Get list of all the devices for this specific adapter.
            devices_uri = join(url, adapter, b"Devices")
            devices = yield self.list_resources(
                devices_uri, headers)
            # Iterate over all the devices for this specific adapter.
            for device in devices:
                device_data = yield self.redfish_request(
                    b"GET", join(url, device), headers)
                storages.append(device_data.get('CapacityGiB'))
        return storages

    @inlineCallbacks
    def scan_machine_memories(
            self, url, headers, system, discovered_machine):
        """Scan machine's memory for the given system."""
        # Get list of all memories for this specific system.
        memories_uri = join(url, system, b"Memory")
        memories = yield self.list_resources(memories_uri, headers)
        # Iterate over all the memories for this specific system.
        for memory in memories:
            memory_data = yield self.redfish_request(
                b"GET", join(url, memory), headers)
            discovered_machine.memory += memory_data.get('CapacityMiB')

    @inlineCallbacks
    def scan_machine_processors(
            self, url, headers, system, discovered_machine):
        """Scan machine's processors for the given system."""
        # Get list of all processors for this specific system.
        processors_uri = join(
            url, system, b"Processors")
        processors = yield self.list_resources(
            processors_uri, headers)
        # Iterate over all processors for this specific system.
        for processor in processors:
            # Get the data for this specific processor.
            processor_data = yield self.redfish_request(
                b"GET", join(url, processor), headers)
            # Using 'TotalThreads' instead of 'TotalCores'
            # as this is what MAAS finds when commissioning.
            discovered_machine.cores += processor_data.get(
                'TotalThreads')
            discovered_machine.cpu_speeds.append(
                processor_data.get('MaxSpeedMHz'))
            # Set architecture to first processor
            # architecture type found.
            if not discovered_machine.architecture:
                arch = processor_data.get('ProcessorArchitecture')
                discovered_machine.architecture = (
                    ARCH_FIX.get(arch, arch))

    @inlineCallbacks
    def scan_machine_local_storage(
            self, url, headers, system, discovered_machine):
        """Scan machine's local storage for the given system."""
        # Get list of all adapters for this specific system.
        adapters_uri = join(url, system, b"Adapters")
        adapters = yield self.list_resources(
            adapters_uri, headers)
        # Iterate over all the adapters for this specific system.
        for adapter in adapters:
            # Get list of all the devices for this specific adapter.
            devices_uri = join(url, adapter, b"Devices")
            devices = yield self.list_resources(
                devices_uri, headers)
            # Iterate over all the devices for this specific adapter.
            for device in devices:
                discovered_machine_block_device = (
                    DiscoveredMachineBlockDevice(
                        model='', serial='', size=0))
                device_data = yield self.redfish_request(
                    b"GET", join(url, device), headers)
                model = device_data.get('Model')
                if model is not None:
                    discovered_machine_block_device.model = model
                serial_number = device_data.get('SerialNumber')
                if serial_number is not None:
                    discovered_machine_block_device.serial = (
                        serial_number)
                storage = device_data.get('CapacityGiB')
                if storage is not None:
                    # GiB to Bytes.
                    discovered_machine_block_device.size = float(
                        storage) * 1073741824
                if device_data.get('Type') == 'SSD':
                    discovered_machine_block_device.tags = ['ssd']
                discovered_machine.block_devices.append(
                    discovered_machine_block_device)

    @inlineCallbacks
    def scan_machine_interfaces(
            self, url, headers, system, discovered_machine):
        """Scan the machine's interfaces for the given system."""
        # Get list of all Ethernet Interfaces for this specific system.
        interfaces_uri = join(url, system, b"EthernetInterfaces")
        interfaces = yield self.list_resources(
            interfaces_uri, headers)
        # Iterate over all the interfaces for this specific system.
        for interface in interfaces:
            discovered_machine_interface = DiscoveredMachineInterface(
                mac_address='')
            # Get the data for this specific interface.
            interface_data = yield self.redfish_request(
                b"GET", join(url, interface), headers)
            mac_address = interface_data.get('MACAddress')
            if mac_address is not None:
                discovered_machine_interface.mac_address = mac_address
            nic_speed = interface_data.get('SpeedMbps')
            if nic_speed is not None:
                if nic_speed < 1000:
                    discovered_machine_interface.tags = ["e%s" % nic_speed]
                elif nic_speed == "1000":
                    discovered_machine_interface.tags = ["1g", "e1000"]
                else:
                    # We know that the Mbps > 1000
                    discovered_machine_interface.tags = [
                        "%s" % (nic_speed / 1000)]
            # Oem can be empty sometimes, so let's check this.
            oem = interface_data.get('Links').get('Oem')
            if oem:
                ports = oem.get('Intel_RackScale').get('NeighborPort')
                if ports is not None:
                    for port in ports.values():
                        port = port.lstrip('/').encode('utf-8')
                        port_data = yield self.redfish_request(
                            b"GET", join(url, port), headers)
                        vlans = port_data.get('Links').get('PrimaryVLAN')
                        if vlans is not None:
                            for vlan in vlans.values():
                                vlan = vlan.lstrip('/').encode('utf-8')
                                vlan_data = yield self.redfish_request(
                                    b"GET", join(url, vlan), headers)
                                vlan_id = vlan_data.get('VLANId')
                                if vlan_id is not None:
                                    discovered_machine_interface.vid = vlan_id
            discovered_machine.interfaces.append(discovered_machine_interface)

    @inlineCallbacks
    def get_pod_resources(self, url, headers):
        """Get the POD resources."""
        discovered_pod = DiscoveredPod(
            architectures=[], cores=0, cpu_speed=0, memory=0,
            local_storage=0, capabilities=[Capabilities.FIXED_LOCAL_STORAGE],
            hints=DiscoveredPodHints(cores=0, cpu_speed=0, memory=0,
                                     local_storage=0, local_disks=0))
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
                url, headers, system)
            # Get processor data for this specific system.
            cores, cpu_speeds, arch = (
                yield self.get_pod_processor_resources(
                    url, headers, system))
            # Get storage data for this specific system.
            storages = yield self.get_pod_storage_resources(
                url, headers, system)

            if (None in (memories + cores + cpu_speeds + storages) or
                    arch is None):
                # Skip this system's data as it is not available.
                maaslog.warning(
                    "RSD system ID '%s' is missing required information."
                    "  System will not be included in discovered resources." %
                    system.decode('utf-8').rsplit('/')[-1])
                continue
            else:
                discovered_pod.architectures.append(
                    ARCH_FIX.get(arch, arch))
                discovered_pod.memory += sum(memories)
                discovered_pod.cores += sum(cores)
                discovered_pod.cpu_speeds.extend(cpu_speeds)
                # GiB to Bytes.
                discovered_pod.local_storage += sum(storages) * 1073741824
                discovered_pod.local_disks += len(storages)

        # Set cpu_speed to max of all found cpu_speeds.
        if len(discovered_pod.cpu_speeds):
            discovered_pod.cpu_speed = max(discovered_pod.cpu_speeds)
        return discovered_pod

    @inlineCallbacks
    def get_pod_machines(self, url, headers):
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
            discovered_machine = DiscoveredMachine(
                architecture="amd64/generic", cores=0, cpu_speed=0,
                memory=0, interfaces=[], block_devices=[],
                power_state="unknown",
                power_parameters={
                    'node_id': node.decode('utf-8').rsplit('/')[-1]})
            # Save list of all cpu_speeds being used by composed nodes
            # that we will use later in our pod hints calculations.
            discovered_machine.cpu_speeds = []
            node_data = yield self.redfish_request(
                b"GET", join(url, node), headers)
            power_state = node_data.get('PowerState')
            if power_state is not None:
                discovered_machine.power_state = RSD_SYSTEM_POWER_STATE.get(
                    power_state)
            # Find specific system that this composed node is linked too.
            systems = node_data.get(
                'Links').get('ComputerSystem').values()
            if systems is not None:
                for system in systems:
                    system = system.lstrip('/').encode('utf-8')
                    yield self.scan_machine_memories(
                        url, headers, system, discovered_machine)
                    yield self.scan_machine_processors(
                        url, headers, system, discovered_machine)
                    yield self.scan_machine_local_storage(
                        url, headers, system, discovered_machine)
                    yield self.scan_machine_interfaces(
                        url, headers, system, discovered_machine)

            # Set cpu_speed to max of all found cpu_speeds.
            if len(discovered_machine.cpu_speeds):
                discovered_machine.cpu_speed = max(
                    discovered_machine.cpu_speeds)
            discovered_machines.append(discovered_machine)
        return discovered_machines

    def get_pod_hints(self, discovered_pod):
        """Gets the discovered pod hints."""
        discovered_pod_hints = DiscoveredPodHints(
            cores=0, cpu_speed=0, memory=0, local_storage=0, local_disks=0)
        used_cores = used_memory = used_storage = used_disks = 0
        for machine in discovered_pod.machines:
            for cpu_speed in machine.cpu_speeds:
                discovered_pod.cpu_speeds.remove(cpu_speed)
            # Delete cpu_speeds place holder.
            del machine.cpu_speeds
            used_cores += machine.cores
            used_memory += machine.memory
            for blk_dev in machine.block_devices:
                used_storage += blk_dev.size
                used_disks += 1

        if len(discovered_pod.cpu_speeds):
            discovered_pod_hints.cpu_speed = max(
                discovered_pod.cpu_speeds)
        discovered_pod_hints.cores = (discovered_pod.cores - used_cores)
        discovered_pod_hints.memory = (discovered_pod.memory - used_memory)
        discovered_pod_hints.local_storage = (
            discovered_pod.local_storage - used_storage)
        return discovered_pod_hints

    @inlineCallbacks
    def discover(self, system_id, context):
        """Discover all resources.

        Returns a defer to a DiscoveredPod object.
        """
        url = self.get_url(context)
        headers = self.make_auth_headers(**context)

        # Discover pod resources.
        discovered_pod = yield self.get_pod_resources(url, headers)

        # Discover composed machines.
        discovered_pod.machines = yield self.get_pod_machines(
            url, headers)

        # Discover pod hints.
        discovered_pod.hints = self.get_pod_hints(discovered_pod)

        # Delete cpu_speeds place holder.
        del discovered_pod.cpu_speeds
        return discovered_pod

    @inlineCallbacks
    def compose(self, system_id, context):
        """Compose machine(s)."""
        raise NotImplementedError

    @inlineCallbacks
    def decompose(self, system_id, context):
        """Decompose machine(s)."""
        raise NotImplementedError

    @inlineCallbacks
    def set_pxe_boot(self, url, node_id, headers):
        """Set the composed machine with node_id to PXE boot."""
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        payload = FileBodyProducer(
            BytesIO(
                json.dumps(
                    {
                        'Boot': {
                            'BootSourceOverrideEnabled': "Once",
                            'BootSourceOverrideTarget': "Pxe"
                        }
                    }).encode('utf-8')))
        yield self.redfish_request(
            b"PATCH", join(url, endpoint), headers, payload)

    @inlineCallbacks
    def get_composed_node_state(self, url, node_id, headers):
        """Return the `ComposedNodeState` of the composed machine."""
        endpoint = b"redfish/v1/Nodes/%s" % node_id
        # Get endpoint data for node_id.
        node_data = yield self.redfish_request(
            b"GET", join(url, endpoint), headers)
        return node_data.get('ComposedNodeState')

    @inlineCallbacks
    def assemble_node(self, url, node_id, headers):
        """Assemble composed machine with node_id."""
        node_state = yield self.get_composed_node_state(
            url, node_id, headers)
        if node_state in ('PoweredOn', 'PoweredOff'):
            # Already assembled.
            return
        elif node_state == 'Allocated':
            # Start assembling.
            endpoint = (
                b"redfish/v1/Nodes/%s/Actions/ComposedNode.Assemble"
                % node_id)
            yield self.redfish_request(
                b"POST", join(url, endpoint), headers)
        elif node_state == 'Failed':
            # Broken system.
            raise PodFatalError(
                "Composed machine at node ID %s has a ComposedNodeState"
                " of Failed." % node_id)

        # Assembling was started. Loop over until the state
        # changes from `Assembling`.
        node_state = yield self.get_composed_node_state(
            url, node_id, headers)
        while node_state == 'Assembling':
            node_state = yield self.get_composed_node_state(
                url, node_id, headers)
        # Check one last time if the state has became `Failed`.
        if node_state == 'Failed':
            # Broken system.
            raise PodFatalError(
                "Composed machine at node ID %s has a ComposedNodeState"
                " of Failed." % node_id)

    @inlineCallbacks
    def power(self, power_change, url, node_id, headers):
        endpoint = b"redfish/v1/Nodes/%s/Actions/ComposedNode.Reset" % node_id
        payload = FileBodyProducer(
            BytesIO(
                json.dumps(
                    {
                        'ResetType': "%s" % power_change
                    }).encode('utf-8')))
        yield self.redfish_request(
            b"POST", join(url, endpoint), headers, payload)

    @asynchronous
    @inlineCallbacks
    def power_on(self, system_id, context):
        """Power on composed machine."""
        url = self.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
        headers = self.make_auth_headers(**context)
        # Set to PXE boot.
        yield self.set_pxe_boot(url, node_id, headers)
        power_state = yield self.power_query(system_id, context)
        # Power off the machine if currently on.
        if power_state == 'on':
            yield self.power("ForceOff", url, node_id, headers)
        # Power on the machine.
        yield self.power("On", url, node_id, headers)

    @asynchronous
    @inlineCallbacks
    def power_off(self, system_id, context):
        """Power off composed machine."""
        url = self.get_url(context)
        node_id = context.get('node_id').encode('utf-8')
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
        node_id = context.get('node_id').encode('utf-8')
        headers = self.make_auth_headers(**context)
        # Make sure the node is assembled for power
        # querying to work.
        yield self.assemble_node(url, node_id, headers)
        # We are now assembled, return the power state.
        node_state = yield self.get_composed_node_state(
            url, node_id, headers)
        if node_state in RSD_NODE_POWER_STATE:
            return RSD_NODE_POWER_STATE[node_state]
        else:
            raise PodActionError(
                "Unknown power state: %s" % node_state)
