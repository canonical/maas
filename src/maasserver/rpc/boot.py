# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for getting the configuration for a booting machine."""

__all__ = [
    "get_config",
]

from maasserver.enum import INTERFACE_TYPE
from maasserver.models import (
    BootResource,
    Config,
    Event,
    RackController,
)
from maasserver.models.interface import (
    Interface,
    PhysicalInterface,
)
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
)
from maasserver.server_address import get_maas_facing_server_address
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.orm import (
    get_one,
    transactional,
)
from provisioningserver.events import EVENT_TYPES
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from provisioningserver.utils.twisted import synchronous


DEFAULT_ARCH = 'i386'


def get_node_from_mac_string(mac_string):
    """Get a Node object from a MAC address string.

    Returns a Node object or None if no node with the given MAC address exists.
    """
    if mac_string is None:
        return None
    interface = get_one(
        Interface.objects.filter(
            type=INTERFACE_TYPE.PHYSICAL, mac_address=mac_string))
    return interface.node if interface else None


def event_log_pxe_request(machine, purpose):
    """Log PXE request to machines's event log."""
    options = {
        'commissioning': "commissioning",
        'xinstall': "installation",
        'local': "local boot",
        'poweroff': "power off",
    }
    Event.objects.create_node_event(
        system_id=machine.system_id, event_type=EVENT_TYPES.NODE_PXE_REQUEST,
        event_description=options[purpose])


@synchronous
@transactional
def get_config(
        system_id, local_ip, remote_ip, arch=None, subarch=None, mac=None,
        bios_boot_method=None):
    """Get the booting configration for the a machine.

    Returns a structure suitable for returning in the response
    for :py:class:`~provisioningserver.rpc.region.GetBootConfig`.

    Raises BootConfigNoResponse when booting machine should fail to next file.
    """
    rack_controller = RackController.objects.get(system_id=system_id)
    machine = get_node_from_mac_string(mac)

    # Fail with no response early so no extra work is performed.
    if machine is None and arch is None and mac is not None:
        # Request was pxelinux.cfg/01-<mac> for a machine MAAS does not know
        # about. So attempt fall back to pxelinux.cfg/default-<arch>-<subarch>
        # for arch detection.
        raise BootConfigNoResponse()

    if machine is not None:
        # Update the last interface, last access cluster IP address, and
        # the last used BIOS boot method. Only saving the fields that have
        # changed on the machine.
        update_fields = []
        if (machine.boot_interface is None or
                machine.boot_interface.mac_address != mac):
            machine.boot_interface = PhysicalInterface.objects.get(
                mac_address=mac)
            update_fields.append("boot_interface")
        if (machine.boot_cluster_ip is None or
                machine.boot_cluster_ip != local_ip):
            machine.boot_cluster_ip = local_ip
            update_fields.append("boot_cluster_ip")
        if machine.bios_boot_method != bios_boot_method:
            machine.bios_boot_method = bios_boot_method
            update_fields.append("bios_boot_method")
        if len(update_fields) > 0:
            machine.save(update_fields=update_fields)

        # Update the VLAN of the boot interface to be the same VLAN for the
        # interface on the rack controller that the machine communicated with.
        rack_interface = rack_controller.interface_set.filter(
            ip_addresses__ip=local_ip).first()
        if (rack_interface is not None and
                machine.boot_interface.vlan != rack_interface.vlan):
            machine.boot_interface.vlan = rack_interface.vlan
            machine.boot_interface.save()

        arch, subarch = machine.split_arch()
        preseed_url = compose_preseed_url(machine, rack_controller)
        hostname = machine.hostname
        domain = machine.domain.name
        purpose = machine.get_boot_purpose()

        # Log the request into the event log for that machine.
        event_log_pxe_request(machine, purpose)

        # Get the correct operating system and series based on the purpose
        # of the booting machine.
        if purpose == "commissioning":
            osystem = Config.objects.get_config('commissioning_osystem')
            series = Config.objects.get_config('commissioning_distro_series')
        else:
            osystem = machine.get_osystem()
            series = machine.get_distro_series()
            if purpose == "xinstall" and osystem != "ubuntu":
                # Use only the commissioning osystem and series, for operating
                # systems other than Ubuntu. As Ubuntu supports HWE kernels,
                # and needs to use that kernel to perform the installation.
                osystem = Config.objects.get_config('commissioning_osystem')
                series = Config.objects.get_config(
                    'commissioning_distro_series')

        # Pre MAAS-1.9 the subarchitecture defined any kernel the machine
        # needed to be able to boot. This could be a hardware enablement
        # kernel(e.g hwe-t) or something like highbank. With MAAS-1.9 any
        # hardware enablement kernel must be specifed in the hwe_kernel field,
        # any other kernel, such as highbank, is still specifed as a
        # subarchitecture. Since Ubuntu does not support architecture specific
        # hardware enablement kernels(i.e a highbank hwe-t kernel on precise)
        # we give precedence to any kernel defined in the subarchitecture field
        if subarch == "generic" and machine.hwe_kernel:
            subarch = machine.hwe_kernel
        elif(subarch == "generic" and
             purpose == "commissioning" and
             machine.min_hwe_kernel):
            subarch = machine.min_hwe_kernel

        # We don't care if the kernel opts is from the global setting or a tag,
        # just get the options
        _, effective_kernel_opts = machine.get_effective_kernel_options()

        # Add any extra options from a third party driver.
        use_driver = Config.objects.get_config('enable_third_party_drivers')
        if use_driver:
            driver = get_third_party_driver(machine)
            driver_kernel_opts = driver.get('kernel_opts', '')

            combined_opts = ('%s %s' % (
                '' if effective_kernel_opts is None else effective_kernel_opts,
                driver_kernel_opts)).strip()
            if len(combined_opts):
                extra_kernel_opts = combined_opts
            else:
                extra_kernel_opts = None
        else:
            extra_kernel_opts = effective_kernel_opts
    else:
        purpose = "commissioning"  # enlistment
        preseed_url = compose_enlistment_preseed_url(rack_controller)
        hostname = 'maas-enlist'
        domain = 'local'
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')
        min_hwe_kernel = Config.objects.get_config('default_min_hwe_kernel')

        # When no architecture is defined for the enlisting machine select
        # the best boot resource for the operating system and series. If
        # none exists fallback to the default architecture. LP #1181334
        if arch is None:
            resource = (
                BootResource.objects.get_default_commissioning_resource(
                    osystem, series))
            if resource is None:
                arch = DEFAULT_ARCH
            else:
                arch, _ = resource.split_arch()
        if subarch is None:
            if min_hwe_kernel:
                subarch = min_hwe_kernel
            else:
                subarch = 'generic'

        # Global kernel options for enlistment.
        extra_kernel_opts = Config.objects.get_config("kernel_opts")

    # Set the final boot purpose.
    if machine is None and arch == DEFAULT_ARCH:
        # If the machine is enlisting and the arch is the default arch (i386),
        # use the dedicated enlistment template which performs architecture
        # detection.
        boot_purpose = "enlist"
    elif purpose == 'poweroff':
        # In order to power the machine off, we need to get it booted in the
        # commissioning environment and issue a `poweroff` command.
        boot_purpose = 'commissioning'
    else:
        boot_purpose = purpose

    # Get the service address to the region for that given rack controller.
    server_address = get_maas_facing_server_address(
        rack_controller=rack_controller)

    # Return the params to the rack controller. Include the system_id only
    # if the machine was known.
    params = {
        "arch": arch,
        "subarch": subarch,
        "osystem": osystem,
        "release": series,
        "purpose": boot_purpose,
        "hostname": hostname,
        "domain": domain,
        "preseed_url": preseed_url,
        "fs_host": local_ip,
        "log_host": server_address,
        "extra_opts": '' if extra_kernel_opts is None else extra_kernel_opts,
    }
    if machine is not None:
        params["system_id"] = machine.system_id
    return params
