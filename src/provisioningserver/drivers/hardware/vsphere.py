# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'power_control_vsphere',
    'power_query_vsphere',
    'probe_vsphere_and_enlist',
    ]

from abc import abstractmethod
from collections import OrderedDict
import traceback

from provisioningserver.logger import get_maas_logger
from provisioningserver.utils import (
    commission_node,
    create_node,
    )
from provisioningserver.utils.twisted import synchronous


try:
    import pyVmomi
    import pyVim.connect as vmomi_api
except ImportError:
    pyVmomi = None
    vmomi_api = None

maaslog = get_maas_logger("drivers.vsphere")


class VsphereError(Exception):
    """Failure talking to the vSphere API. """


class VsphereAPI(object):
    """Abstract base class to represent a MAAS-capable VMware API. The API
    must be capable of:
    - Gathering names, UUID, and MAC addresses of each virtual machine
    - Powering on/off VMs
    - Checking the power status of VMs
    """
    def __init__(self, host, username, password,
                 port=None, protocol=None):
        """
        :param host: The vSphere host to connect to
        :type host: string
        :param port: The port on the vSphere host to connect to
        :type port: integer
        :param username: A username authorized for the specified vSphere host
        :type username: string
        :param password: The password corresponding to the supplied username
        :type password: string
        :param protocol: The protocol to use (default: 'https')
        :type protocol: string
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.protocol = protocol

    @abstractmethod
    def connect(self):
        """Connects to the vSphere API"""
        raise NotImplementedError

    @abstractmethod
    def is_connected(self):
        """Returns True if the vSphere API is thought to be connected"""
        raise NotImplementedError

    def disconnect(self):
        """Disconnects from the vSphere API"""
        raise NotImplementedError

    @abstractmethod
    def find_vm_by_uuid(self, uuid):
        """
        Searches for a VM that matches the specified UUID. The UUID can be
        either an instance UUID, or a BIOS UUID. If found, returns an object
        to represent the VM. Otherwise, returns None.
        :return: an opaque object representing the VM
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def get_maas_power_state(vm):
        """
        Returns the MAAS representation of the power status for the
        specified virtual machine.
        :return: string ('on', 'off', or 'error')
        """
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def set_power_state(vm, power_change):
        """
        Sets the power state for the specified VM to the specified value.
        :param:power_change: the new desired state ('on' or 'off')
        :except:VsphereError: if the power status could not be changed
        """
        raise NotImplementedError

    @abstractmethod
    def get_all_vm_properties(self):
        """
        Creates dictionary that catalogs every virtual machine present on
        the vSphere server. Each key is a machine name, and each value is a
        dictionary containing the following keys:
         - uuid: a UUID for the VM (to be used for power management)
         - macs: a list of MAC addresses associated with this VM
         - architecture: amd64 or i386 (depending on the guest ID)
         - power_state: the current power state of the VM ("on" or "off")
        :return: a dictionary as specified above
        """
        raise NotImplementedError


class VspherePyvmomi(VsphereAPI):
    def __init__(
            self, host, username, password, port=None, protocol=None):
        super(VspherePyvmomi, self).__init__(host, username, password,
                                             port=port, protocol=protocol)
        self.service_instance = None

    def connect(self):
        # place optional arguments in a dictionary to pass to the
        # VMware API call; otherwise the API will see 'None' and fail.
        extra_args = {}
        if self.port is not None:
            extra_args['port'] = self.port

        if self.protocol is not None:
            extra_args['protocol'] = self.protocol

        self.service_instance = vmomi_api.SmartConnect(host=self.host,
                                                       user=self.username,
                                                       pwd=self.password,
                                                       **extra_args)

        if not self.service_instance:
            raise VsphereError("Could not connect to vSphere service API")

        return self.service_instance is not None

    def is_connected(self):
        return self.service_instance is not None

    def disconnect(self):
        vmomi_api.Disconnect(self.service_instance)
        self.service_instance = None

    @staticmethod
    def _probe_network_cards(vm):
        mac_addresses = []
        for device in vm.config.hardware.device:
            if hasattr(device, 'macAddress'):
                mac = device.macAddress
                if mac is not None and mac != "":
                    mac_addresses.append(mac)
        return mac_addresses

    @staticmethod
    def _get_uuid(vm):
        # In vCenter environments, using the BIOS UUID (uuid) is deprecated.
        # But we can use it as a fallback, since the API supports both.
        if hasattr(vm.summary.config, 'instanceUuid') \
                and vm.summary.config.instanceUuid is not None:
            return vm.summary.config.instanceUuid
        elif hasattr(vm.summary.config, 'uuid') \
                and vm.summary.config.uuid is not None:
            return vm.summary.config.uuid
        return None

    def find_vm_by_uuid(self, uuid):
        content = self.service_instance.RetrieveContent()

        # First search using the instance UUID
        vm = content.searchIndex.FindByUuid(None, uuid, True, True)

        if vm is None:
            # ... otherwise, try using the BIOS UUID
            vm = content.searchIndex.FindByUuid(None, uuid, True, False)
        return vm

    @staticmethod
    def _get_power_state(vm):
        return vm.runtime.powerState

    @staticmethod
    def pyvmomi_to_maas_powerstate(power_state):
        """Returns a MAAS power state given the specified pyvmomi state"""
        if power_state == 'poweredOn':
            return "on"
        elif power_state == 'poweredOff':
            return "off"
        elif power_state == 'suspended':
            return "on"  # TODO: model this in MAAS
        else:
            return "error"

    @staticmethod
    def get_maas_power_state(vm):
        return VspherePyvmomi.pyvmomi_to_maas_powerstate(vm.runtime.powerState)

    @staticmethod
    def set_power_state(vm, power_change):
        if vm is not None:
            if power_change == 'on':
                vm.PowerOn()
            elif power_change == 'off':
                vm.PowerOff()
            else:
                raise VsphereError("set_power_state: Invalid power_change "
                                   "state: {state}".format(power_change))

    def _get_vm_properties(self, vm):
        """Gathers the properties for the specified VM, for inclusion into
        the dictionary containing the properties of all VMs."""
        properties = {}

        properties['uuid'] = self._get_uuid(vm)

        if "64" in vm.summary.config.guestId:
            properties['architecture'] = "amd64"
        else:
            properties['architecture'] = "i386"

        properties['power_state'] = self.pyvmomi_to_maas_powerstate(
            self._get_power_state(vm))

        properties['macs'] = self._probe_network_cards(vm)

        # These aren't needed now, but we might want them one day...
        # properties['cpus'] = vm.summary.config.numCpu
        # properties['ram'] = vm.summary.config.memorySizeMB

        return properties

    def get_all_vm_properties(self):
        # Using an OrderedDict() in case the order that virtual machines
        # are returned in is important to the user.
        virtual_machines = OrderedDict()

        content = self.service_instance.RetrieveContent()
        for child in content.rootFolder.childEntity:
            if hasattr(child, 'vmFolder'):
                datacenter = child
                vm_folder = datacenter.vmFolder
                vm_list = vm_folder.childEntity
                for vm in vm_list:
                    vm_name = vm.summary.config.name
                    vm_properties = self._get_vm_properties(vm)
                    virtual_machines[vm_name] = vm_properties

        return virtual_machines


def _get_vsphere_api(
        host, username, password, port=None, protocol=None):
    if pyVmomi is not None:
        # Attempt to detect the best available VMware API
        return VspherePyvmomi(
            host, username, password, port=port, protocol=protocol)
    else:
        raise VsphereError("Could not find a suitable "
                           "vSphere API (install python-pyvmomi)")


def get_vsphere_servers(
        host, username, password, port=None, protocol=None):
    servers = {}
    api = _get_vsphere_api(
        host, username, password, port=port, protocol=protocol)

    if api.connect():
        try:
            servers = api.get_all_vm_properties()
        finally:
            api.disconnect()
    return servers


@synchronous
def probe_vsphere_and_enlist(
        user, host, username, password, port=None,
        protocol=None, prefix_filter=None, accept_all=False):

    # Both '' and None mean the same thing, so normalize it.
    if prefix_filter is None:
        prefix_filter = ''

    servers = get_vsphere_servers(host, username, password, port=port,
                                  protocol=protocol)

    maaslog.info("Found %d vSphere servers", len(servers))

    for system_name in servers:
        if not system_name.startswith(prefix_filter):
            maaslog.info(
                "Skipping node named '%s'; does not match prefix filter '%s'",
                system_name, prefix_filter)
            continue
        properties = servers[system_name]
        params = {
            'power_uuid': properties['uuid'],
            'power_address': host,
            'power_port': port,
            'power_protocol': protocol,
            'power_user': username,
            'power_pass': password,
        }
        maaslog.info(
            "Creating vSphere node with MACs: %s", properties['macs'])

        system_id = create_node(properties['macs'], properties['architecture'],
                                'vsphere', params).wait(30)

        if accept_all and system_id is not None:
            commission_node(system_id, user).wait(30)


def power_control_vsphere(
        host, username, password, uuid, power_change,
        port=None, protocol=None):
    api = _get_vsphere_api(
        host, username, password, port=port, protocol=protocol)

    if api.connect():
        try:
            vm = api.find_vm_by_uuid(uuid)
            if vm is None:
                raise VsphereError("Failed to find VM based on UUID: {uuid}"
                                   .format(uuid=uuid))

            api.set_power_state(vm, power_change)
        except:
            raise VsphereError(
                "Failed to set power state to {state} for uuid={uuid}"
                .format(state=power_change, uuid=uuid), traceback.format_exc())
        finally:
            api.disconnect()


def power_query_vsphere(
        host, username, password, uuid, port=None, protocol=None):
    """Return the power state for the VM with the specified UUID,
     using the vSphere API."""
    api = _get_vsphere_api(
        host, username, password, port=port, protocol=protocol)

    if api.connect():
        try:
            vm = api.find_vm_by_uuid(uuid)
            if vm is not None:
                return api.get_maas_power_state(vm)
        except:
            raise VsphereError(
                "Failed to get power state for uuid={uuid}"
                .format(uuid=uuid), traceback.format_exc())
        finally:
            api.disconnect()
