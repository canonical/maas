# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
from importlib import import_module
from inspect import getcallargs
import ssl
import traceback
from typing import Optional
from urllib.parse import unquote

from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.utils import commission_node, create_node
from provisioningserver.utils.twisted import synchronous

vmomi_api = None
vim = None

maaslog = get_maas_logger("drivers.vmware")


def try_pyvmomi_import():
    """Attempt to import the pyVmomi API. This API is provided by the
    python3-pyvmomi package; if it doesn't work out, we need to notify
    the user so they can install it.
    """
    global vim
    global vmomi_api
    try:
        if vim is None:
            vim_module = import_module("pyVmomi")
            vim = getattr(vim_module, "vim")
        if vmomi_api is None:
            vmomi_api = import_module("pyVim.connect")
    except ImportError:
        return False
    else:
        return True


class VMwareAPIException(Exception):
    """Failure talking to the VMware API."""


class VMwareVMNotFound(VMwareAPIException):
    """The specified virtual machine was not found."""


class VMwareClientNotFound(VMwareAPIException):
    """A usable VMware API client was not found."""


class VMwareAPIConnectionFailed(VMwareAPIException):
    """The VMware API endpoint could not be contacted."""


class VMwareAPI(metaclass=ABCMeta):
    """Abstract base class to represent a MAAS-capable VMware API. The API
    must be capable of:
    - Gathering names, UUID, and MAC addresses of each virtual machine
    - Powering on/off VMs
    - Checking the power status of VMs
    """

    def __init__(self, host, username, password, port=None, protocol=None):
        """
        :param host: The VMware host to connect to
        :type host: string
        :param port: The port on the VMware host to connect to
        :type port: integer
        :param username: A username authorized for the specified VMware host
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
        """Connects to the VMware API"""
        raise NotImplementedError

    @abstractmethod
    def is_connected(self):
        """Returns True if the VMware API is thought to be connected"""
        raise NotImplementedError

    @abstractmethod
    def disconnect(self):
        """Disconnects from the VMware API"""
        raise NotImplementedError

    @abstractmethod
    def is_folder(self, obj):
        """Returns true if the specified API object is a Folder."""
        raise NotImplementedError

    @abstractmethod
    def is_datacenter(self, obj):
        """Returns true if the specified API object is a Datacenter."""
        raise NotImplementedError

    @abstractmethod
    def is_vm(self, obj):
        """Returns true if the specified API object is a VirtualMachine."""
        raise NotImplementedError

    @abstractmethod
    def has_children(self, obj):
        """Returns true if the specified API object has children.

        This is used to determine if it should be traversed in order to look
        for more virutal machines.
        """
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

    @abstractmethod
    def get_maas_power_state(self, vm):
        """
        Returns the MAAS representation of the power status for the
        specified virtual machine.
        :return: string ('on', 'off', or 'error')
        """
        raise NotImplementedError

    @abstractmethod
    def set_power_state(self, vm, power_change):
        """
        Sets the power state for the specified VM to the specified value.
        :param:power_change: the new desired state ('on' or 'off')
        :except:VMwareError: if the power status could not be changed
        """
        raise NotImplementedError

    @abstractmethod
    def get_all_vm_properties(self):
        """
        Creates dictionary that catalogs every virtual machine present on
        the VMware server. Each key is a machine name, and each value is a
        dictionary containing the following keys:
         - uuid: a UUID for the VM (to be used for power management)
         - macs: a list of MAC addresses associated with this VM
         - architecture: amd64 or i386 (depending on the guest ID)
         - power_state: the current power state of the VM ("on" or "off")
        :return: a dictionary as specified above
        """
        raise NotImplementedError


class VMwarePyvmomiAPI(VMwareAPI):
    def __init__(self, host, username, password, port=None, protocol=None):
        super().__init__(
            host, username, password, port=port, protocol=protocol
        )
        self.service_instance = None

    def connect(self):
        # Place optional arguments in a dictionary to pass to the
        # VMware API call; otherwise the API will see 'None' and fail.
        extra_args = {}
        if self.port is not None:
            extra_args["port"] = self.port
        if self.protocol is not None:
            if self.protocol == "https+unverified":
                # This is a workaround for using untrusted certificates.
                extra_args["protocol"] = "https"
                if "sslContext" in getcallargs(vmomi_api.SmartConnect):
                    context = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
                    context.verify_mode = ssl.CERT_NONE
                    extra_args["sslContext"] = context
                else:
                    maaslog.error(
                        "Unable to use unverified SSL context to connect to "
                        "'%s'. (In order to use this feature, you must update "
                        "to a more recent version of the python3-pyvmomi "
                        "package.)" % self.host
                    )
                    raise VMwareAPIException(
                        "Failed to set up unverified SSL context. Please "
                        "update to a more recent version of the "
                        "python3-pyvmomi package."
                    )
            else:
                extra_args["protocol"] = self.protocol
        self.service_instance = vmomi_api.SmartConnect(
            host=self.host, user=self.username, pwd=self.password, **extra_args
        )
        if not self.service_instance:
            raise VMwareAPIConnectionFailed(
                "Could not connect to VMware service API"
            )
        return self.service_instance is not None

    def is_folder(self, obj):
        return isinstance(obj, vim.Folder)

    def is_datacenter(self, obj):
        return isinstance(obj, vim.Datacenter)

    def is_vm(self, obj):
        return isinstance(obj, vim.VirtualMachine)

    def has_children(self, obj):
        return isinstance(obj, (vim.Folder, vim.Datacenter))

    def is_connected(self):
        return self.service_instance is not None

    def disconnect(self):
        vmomi_api.Disconnect(self.service_instance)
        self.service_instance = None

    def _probe_network_cards(self, vm):
        """Returns a list of MAC addresses for this VM, followed by a list
        of unique keys that VMware uses to uniquely identify the NICs. The
        MAC addresses are used to create the node. If the node is created
        successfully, the keys will be used to set the boot order on the
        virtual machine."""
        mac_addresses = []
        nic_keys = []
        for device in vm.config.hardware.device:
            if hasattr(device, "macAddress"):
                mac = device.macAddress
                if mac is not None and mac != "":
                    mac_addresses.append(mac)
                    nic_keys.append(device.key)
        return mac_addresses, nic_keys

    def _get_uuid(self, vm):
        # In vCenter environments, using the BIOS UUID (uuid) is deprecated.
        # But we can use it as a fallback, since the API supports both.
        if (
            hasattr(vm.summary.config, "instanceUuid")
            and vm.summary.config.instanceUuid is not None
        ):
            return vm.summary.config.instanceUuid
        elif (
            hasattr(vm.summary.config, "uuid")
            and vm.summary.config.uuid is not None
        ):
            return vm.summary.config.uuid
        return None

    def _find_virtual_machines(self, parent):
        vms = []
        if self.is_datacenter(parent):
            children = parent.vmFolder.childEntity
        elif self.is_folder(parent):
            children = parent.childEntity
        else:
            raise ValueError("Unknown type: %s" % type(parent))
        for child in children:
            if self.is_vm(child):
                vms.append(child)
            elif self.has_children(child):
                vms.extend(self._find_virtual_machines(child))
            else:
                print("Unknown type: %s" % type(child))
        return vms

    def _get_vm_list(self):
        content = self.service_instance.RetrieveContent()
        root_folder = content.rootFolder
        return self._find_virtual_machines(root_folder)

    def find_vm_by_name(self, vm_name):
        vm_list = self._get_vm_list()
        for vm in vm_list:
            if vm_name == vm.summary.config.name:
                return vm
        return None

    def find_vm_by_uuid(self, uuid):
        content = self.service_instance.RetrieveContent()

        # First search using the instance UUID
        vm = content.searchIndex.FindByUuid(None, uuid, True, True)

        if vm is None:
            # ... otherwise, try using the BIOS UUID
            vm = content.searchIndex.FindByUuid(None, uuid, True, False)
        return vm

    def _get_power_state(self, vm):
        return vm.runtime.powerState

    def pyvmomi_to_maas_powerstate(self, power_state):
        """Returns a MAAS power state given the specified pyvmomi state"""
        if power_state == "poweredOn":
            return "on"
        elif power_state == "poweredOff":
            return "off"
        elif power_state == "suspended":
            return "on"  # TODO: model this in MAAS
        else:
            return "error"

    def get_maas_power_state(self, vm):
        return self.pyvmomi_to_maas_powerstate(vm.runtime.powerState)

    def set_power_state(self, vm, power_change):
        if vm is not None:
            if power_change == "on":
                vm.PowerOn()
            elif power_change == "off":
                vm.PowerOff()
            else:
                raise ValueError(
                    f"set_power_state: Invalid power_change state: {power_change}"
                )

    def set_pxe_boot(self, vm_properties):
        boot_devices = []
        for nic in vm_properties["nics"]:
            boot_nic = vim.vm.BootOptions.BootableEthernetDevice()
            boot_nic.deviceKey = nic
            boot_devices.append(boot_nic)
        if len(boot_devices) > 0:
            vmconf = vim.vm.ConfigSpec()
            vmconf.bootOptions = vim.vm.BootOptions(bootOrder=boot_devices)
            # use the reference to the VM we stashed away in the properties
            vm_properties["this"].ReconfigVM_Task(vmconf)

    def _get_vm_properties(self, vm):
        """Gathers the properties for the specified VM, for inclusion into
        the dictionary containing the properties of all VMs."""
        properties = {}

        properties["this"] = vm
        properties["uuid"] = self._get_uuid(vm)

        if "64" in vm.summary.config.guestId:
            properties["architecture"] = "amd64"
        else:
            properties["architecture"] = "i386"

        properties["power_state"] = self.pyvmomi_to_maas_powerstate(
            self._get_power_state(vm)
        )

        properties["macs"], properties["nics"] = self._probe_network_cards(vm)

        # These aren't needed now, but we might want them one day...
        # properties['cpus'] = vm.summary.config.numCpu
        # properties['ram'] = vm.summary.config.memorySizeMB

        return properties

    def get_all_vm_properties(self):
        # Using an OrderedDict() in case the order that virtual machines
        # are returned in is important to the user.
        virtual_machines = OrderedDict()

        vm_list = self._get_vm_list()
        for vm in vm_list:
            vm_name = vm.summary.config.name
            vm_properties = self._get_vm_properties(vm)
            virtual_machines[vm_name] = vm_properties

        return virtual_machines


def _get_vmware_api(host, username, password, port=None, protocol=None):
    if try_pyvmomi_import():
        # Attempt to detect the best available VMware API
        return VMwarePyvmomiAPI(
            host, username, password, port=port, protocol=protocol
        )
    else:
        raise VMwareClientNotFound(
            "Could not find a suitable VMware API (install python3-pyvmomi)"
        )


def get_vmware_servers(host, username, password, port=None, protocol=None):
    servers = {}
    api = _get_vmware_api(
        host, username, password, port=port, protocol=protocol
    )

    if api.connect():
        try:
            servers = api.get_all_vm_properties()
        finally:
            api.disconnect()
    return servers


@synchronous
def probe_vmware_and_enlist(
    user: str,
    host: str,
    username: Optional[str],
    password: Optional[str],
    port: int = None,
    protocol: str = None,
    prefix_filter: str = None,
    accept_all: bool = False,
    domain: str = None,
):
    # Both '' and None mean the same thing, so normalize it.
    if prefix_filter is None:
        prefix_filter = ""

    api = _get_vmware_api(
        host, username, password, port=port, protocol=protocol
    )

    if api.connect():
        try:
            servers = api.get_all_vm_properties()
            _probe_and_enlist_vmware_servers(
                api,
                accept_all,
                host,
                password,
                port,
                prefix_filter,
                protocol,
                servers,
                user,
                username,
                domain,
            )
        finally:
            api.disconnect()


def _probe_and_enlist_vmware_servers(
    api,
    accept_all,
    host,
    password,
    port,
    prefix_filter,
    protocol,
    servers,
    user,
    username,
    domain,
):
    maaslog.info("Found %d VMware servers", len(servers))
    for system_name in servers:
        if not system_name.startswith(prefix_filter):
            maaslog.info(
                "Skipping node named '%s'; does not match prefix filter '%s'",
                system_name,
                prefix_filter,
            )
            continue
        properties = servers[system_name]
        params = {
            "power_vm_name": system_name,
            "power_uuid": properties["uuid"],
            "power_address": host,
            "power_port": port,
            "power_protocol": protocol,
            "power_user": username,
            "power_pass": password,
        }

        # Note: the system name is URL encoded, so before we go to log
        # and/or create the node, we need to unquote it.
        # Otherwise we might pass in names like "Ubuntu%20(64-bit)"
        system_name = unquote(system_name)
        maaslog.info(
            "Creating VMware node with MACs: %s (%s)",
            properties["macs"],
            system_name,
        )

        system_id = create_node(
            properties["macs"],
            properties["architecture"],
            "vmware",
            params,
            domain,
            system_name,
        ).wait(30)

        if system_id is not None:
            api.set_pxe_boot(properties)

        if accept_all and system_id is not None:
            commission_node(system_id, user).wait(30)


def _find_vm_by_uuid_or_name(api, uuid, vm_name):
    if uuid:
        vm = api.find_vm_by_uuid(uuid)
    elif vm_name:
        vm = api.find_vm_by_name(vm_name)
    else:
        raise VMwareVMNotFound(
            "Failed to find VM; need a UUID or a VM name for power control"
        )
    return vm


def power_control_vmware(
    host,
    username,
    password,
    vm_name,
    uuid,
    power_change,
    port=None,
    protocol=None,
):
    api = _get_vmware_api(
        host, username, password, port=port, protocol=protocol
    )

    if api.connect():
        try:
            vm = _find_vm_by_uuid_or_name(api, uuid, vm_name)

            if vm is None:
                raise VMwareVMNotFound(
                    "Failed to find VM; uuid={uuid}, name={name}".format(
                        uuid=uuid, name=vm_name
                    )
                )

            api.set_power_state(vm, power_change)
        except VMwareAPIException:
            raise
        except Exception:
            # This is to cover what might go wrong in set_power_state(), if
            # an exception occurs while poweriing on or off.
            raise VMwareAPIException(
                "Failed to set power state to {state} for uuid={uuid}".format(
                    state=power_change, uuid=uuid
                ),
                traceback.format_exc(),
            )
        finally:
            api.disconnect()


def power_query_vmware(
    host, username, password, vm_name, uuid, port=None, protocol=None
):
    """Return the power state for the VM with the specified UUID,
    using the VMware API."""
    api = _get_vmware_api(
        host, username, password, port=port, protocol=protocol
    )

    if api.connect():
        try:
            vm = _find_vm_by_uuid_or_name(api, uuid, vm_name)
            if vm is not None:
                return api.get_maas_power_state(vm)
        except VMwareAPIException:
            raise
        except Exception:
            raise VMwareAPIException(
                f"Failed to get power state for uuid={uuid}",
                traceback.format_exc(),
            )
        finally:
            api.disconnect()
