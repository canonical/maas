# Copyright 2016-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC helpers for getting the configuration for a booting machine."""


import re
import shlex

from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db.models import Q

from maasserver.compose_preseed import RSYSLOG_PORT
from maasserver.dns.config import get_resource_name_for_subnet
from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, INTERFACE_TYPE
from maasserver.fields import normalise_macaddress
from maasserver.models import (
    BootResource,
    Config,
    Event,
    Node,
    RackController,
    Subnet,
    VLAN,
)
from maasserver.node_status import NODE_STATUS
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
)
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils.orm import transactional
from maasserver.utils.osystems import get_working_kernel
from provisioningserver.events import EVENT_TYPES
from provisioningserver.logger import get_maas_logger
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from provisioningserver.utils.network import get_source_address
from provisioningserver.utils.twisted import synchronous, undefined
from provisioningserver.utils.url import splithost

maaslog = get_maas_logger("rpc.boot")


DEFAULT_ARCH = "i386"


def get_node_from_mac_or_hardware_uuid(mac=None, hardware_uuid=None):
    """Get a Node object from a MAC address or hardware UUID string.

    Returns a Node object or None if no node with the given MAC address or
    hardware UUID exists.
    """
    if mac:
        if "-" in mac:
            mac = normalise_macaddress(mac)

        q = Q(
            current_config__interface__type=INTERFACE_TYPE.PHYSICAL,
            current_config__interface__mac_address=mac,
        )

        if hardware_uuid:
            q |= Q(hardware_uuid__iexact=hardware_uuid)

        node = Node.objects.filter(q)
    elif hardware_uuid:
        node = Node.objects.filter(hardware_uuid__iexact=hardware_uuid)
    else:
        return None
    node = node.select_related("boot_interface", "domain", "current_config")
    return node.first()


def event_log_pxe_request(machine, purpose):
    """Log PXE request to machines's event log."""
    options = {
        "commissioning": "commissioning",
        "rescue": "rescue mode",
        "xinstall": "installation",
        "ephemeral": "ephemeral",
        "local": "local boot",
        "poweroff": "power off",
    }
    Event.objects.create_node_event(
        machine,
        event_type=EVENT_TYPES.NODE_PXE_REQUEST,
        event_description=options[purpose],
    )
    # Create a status message for performing a PXE boot.
    Event.objects.create_node_event(
        machine, event_type=EVENT_TYPES.PERFORMING_PXE_BOOT
    )


def get_boot_filenames(
    arch,
    subarch,
    osystem,
    series,
    commissioning_osystem=undefined,
    commissioning_distro_series=undefined,
):
    """Return the filenames of the kernel, initrd, and boot_dtb for the boot
    resource."""
    if subarch == "generic":
        # MAAS doesn't store in the BootResource table what subarch is the
        # generic subarch so lookup what the generic subarch maps to.
        try:
            boot_resource_subarch = get_working_kernel(
                subarch,
                None,
                f"{arch}/{subarch}",
                osystem,
                series,
                commissioning_osystem=commissioning_osystem,
                commissioning_distro_series=commissioning_distro_series,
            )
        except ValidationError:
            # It's possible that no kernel's exist at all for this arch,
            # subarch, osystem, series combination. In that case just fallback
            # to 'generic'.
            boot_resource_subarch = "generic"
    else:
        boot_resource_subarch = subarch

    try:
        # Get the filename for the kernel, initrd, and boot_dtb the rack should
        # use when booting.
        boot_resource = BootResource.objects.get(
            architecture=f"{arch}/{boot_resource_subarch}",
            name=f"{osystem}/{series}",
        )
        boot_resource_set = boot_resource.get_latest_complete_set()
        boot_resource_files = {
            bfile.filetype: bfile.filename
            for bfile in boot_resource_set.files.all()
        }
    except ObjectDoesNotExist:
        # If a filename can not be found return None to allow the rack to
        # figure out what todo.
        return None, None, None
    kernel = boot_resource_files.get(BOOT_RESOURCE_FILE_TYPE.BOOT_KERNEL)
    initrd = boot_resource_files.get(BOOT_RESOURCE_FILE_TYPE.BOOT_INITRD)
    boot_dtb = boot_resource_files.get(BOOT_RESOURCE_FILE_TYPE.BOOT_DTB)
    return kernel, initrd, boot_dtb


def merge_kparams_with_extra(kparams, extra_kernel_opts):
    if kparams is None or kparams == "":
        return extra_kernel_opts

    """
    This section will merge the kparams with the extra opts. Our goal is to
    start with what is in kparams and then look to extra_opts for anything
    to add to or override settings in kparams. Anything in extra_opts, which
    can be set through tags, takes precedence so we use that to start with.
    """
    final_params = ""
    if extra_kernel_opts is not None and extra_kernel_opts != "":
        # We need to remove spaces from the tempita subsitutions so the split
        #  command works as desired.
        final_params = re.sub(
            r"{{\s*([\w\.]*)\s*}}", r"{{\g<1>}}", extra_kernel_opts
        )

    # Need to get a list of all kernel params in the extra opts.
    elist = []
    if len(final_params) > 0:
        tmp = shlex.split(final_params)
        for tparam in tmp:
            idx = tparam.find("=")
            key = tparam[0:idx]
            elist.append(key)

    # Go through all the kernel params as normally set.
    new_kparams = re.sub(r"{{\s*([\w\.]*)\s*}}", r"{{\g<1>}}", kparams)
    params = shlex.split(new_kparams)
    for param in params:
        idx = param.find("=")
        key = param[0:idx]
        value = param[idx + 1 : len(param)]

        # The call to split will remove quotes, so we add them back in if
        #  needed.
        if value.find(" ") > 0:
            value = '"' + value + '"'

        # if the param is not in extra_opts, use the one from here.
        if key not in elist:
            final_params = final_params + " " + key + "=" + value

    return final_params


def get_boot_config_for_machine(machine, configs, purpose):
    """Get the correct operating system and series based on the purpose
    of the booting machine.
    """
    _, subarch = machine.split_arch()
    precise = False
    use_machine_hwe_kernel = True
    if purpose == "commissioning":
        # LP: #1768321 - Fix a regression introduced by, and really fix
        # the issue that LP: #1730525 was meant to fix. This ensures that
        # when DISK_ERASING, or when ENTERING_RESCUE_MODE on a deployed
        # machine it uses the OS from the deployed system for the
        # ephemeral environment.
        if machine.osystem == "ubuntu" and (
            machine.status == NODE_STATUS.DISK_ERASING
            or (
                machine.status
                in [NODE_STATUS.ENTERING_RESCUE_MODE, NODE_STATUS.RESCUE_MODE]
                and machine.previous_status == NODE_STATUS.DEPLOYED
            )
        ):
            osystem = machine.get_osystem(default=configs["default_osystem"])
            series = machine.get_distro_series(
                default=configs["default_distro_series"]
            )
        else:
            osystem = configs["commissioning_osystem"]
            series = configs["commissioning_distro_series"]
            # LP:2013529, machine HWE kernel might not exist for
            # commissioning osystem/series
            use_machine_hwe_kernel = False
    else:
        osystem = machine.get_osystem(default=configs["default_osystem"])
        series = machine.get_distro_series(
            default=configs["default_distro_series"]
        )
        # XXX: roaksoax LP: #1739761 - Since the switch to squashfs (and
        # drop of iscsi), precise is no longer deployable. To address a
        # squashfs image is made available allowing it to be deployed in
        # the commissioning ephemeral environment.
        precise = series == "precise"
        if purpose == "xinstall" and (osystem != "ubuntu" or precise):
            install_image = None

            if osystem == "custom":
                # Note: `series` actually contains a name of the
                # custom image in this context.
                install_image = BootResource.objects.get(name=series)
                osystem, series = install_image.split_base_image()
                # LP:2013529, machine HWE kernel might not exist for
                # given base image
                use_machine_hwe_kernel = False

            if install_image is None or osystem != "ubuntu":
                # Use only the commissioning osystem and series, for operating
                # systems other than Ubuntu. As Ubuntu supports HWE kernels,
                # and needs to use that kernel to perform the installation.
                osystem = configs["commissioning_osystem"]
                series = configs["commissioning_distro_series"]
                # LP:2013529, machine HWE kernel might not exist for
                # commissioning osystem/series
                use_machine_hwe_kernel = False

    # Pre MAAS-1.9 the subarchitecture defined any kernel the machine
    # needed to be able to boot. This could be a hardware enablement
    # kernel(e.g hwe-t) or something like highbank. With MAAS-1.9 any
    # hardware enablement kernel must be specifed in the hwe_kernel field,
    # any other kernel, such as highbank, is still specifed as a
    # subarchitecture. Since Ubuntu does not support architecture specific
    # hardware enablement kernels(i.e a highbank hwe-t kernel on precise)
    # we give precedence to any kernel defined in the subarchitecture field

    # XXX: roaksoax LP: #1739761 - Do not override the subarch (used for
    # the deployment ephemeral env) when deploying precise, provided that
    # it uses the commissioning distro_series and hwe kernels are not
    # needed.

    use_machine_hwe_kernel = use_machine_hwe_kernel and (
        machine.hwe_kernel and not precise
    )

    # If the machine is deployed, hardcode the use of the Minimum HWE Kernel
    # This is to ensure that machines can always do testing regardless of
    # what they were deployed with, using the defaults from the settings
    testing_from_deployed = (
        machine.previous_status == NODE_STATUS.DEPLOYED
        and machine.status == NODE_STATUS.TESTING
        and purpose == "commissioning"
    )

    if testing_from_deployed:
        subarch = (
            subarch
            if not configs["default_min_hwe_kernel"]
            else configs["default_min_hwe_kernel"]
        )
    elif use_machine_hwe_kernel:
        subarch = machine.hwe_kernel

    try:
        subarch = get_working_kernel(
            subarch,
            machine.min_hwe_kernel,
            machine.architecture,
            osystem,
            series,
        )
    except ValidationError:
        # In case the kernel for that particular subarch
        # was not found, and no specific kernel was requested,
        # try our best to find a suitable one
        if not use_machine_hwe_kernel:
            try:
                subarch = get_working_kernel(
                    None,
                    machine.min_hwe_kernel,
                    machine.architecture,
                    osystem,
                    series,
                )
            except ValidationError:
                subarch = "no-such-kernel"
        else:
            subarch = "no-such-kernel"

    return osystem, series, subarch


def get_base_url_for_local_ip(local_ip, internal_domain):
    """Get the base URL for the preseed using the `local_ip`."""
    subnet = Subnet.objects.get_best_subnet_for_ip(local_ip)
    if subnet is not None and not subnet.dns_servers and subnet.vlan.dhcp_on:
        # Use the MAAS internal domain to resolve the IP address of
        # the rack controllers on the subnet.
        return "http://{}.{}:5248/".format(
            get_resource_name_for_subnet(subnet),
            internal_domain,
        )
    else:
        # Either no subnet, the subnet has DNS servers defined, or the VLAN
        # that the subnet belongs to doesn't have DHCP enabled. In
        # that case fallback to using IP address only.
        return "http://%s:5248/" % local_ip


def get_final_boot_purpose(machine, arch, purpose):
    """Return the final boot purpose."""
    if machine is None and arch == DEFAULT_ARCH:
        # If the machine is enlisting and the arch is the default arch (i386),
        # use the dedicated enlistment template which performs architecture
        # detection.
        return "enlist"
    elif purpose == "poweroff":
        # In order to power the machine off, we need to get it booted in the
        # commissioning environment and issue a `poweroff` command.
        return "commissioning"
    else:
        return purpose


@synchronous
@transactional
def get_config(
    system_id,
    local_ip,
    remote_ip,
    arch=None,
    subarch=None,
    mac=None,
    hardware_uuid=None,
    bios_boot_method=None,
):
    """Get the booting configration for a machine.

    Returns a structure suitable for returning in the response
    for :py:class:`~provisioningserver.rpc.region.GetBootConfig`.

    Raises BootConfigNoResponse when booting machine should fail to next file.
    """
    rack_controller = RackController.objects.get(system_id=system_id)
    region_ip = None
    if remote_ip is not None:
        region_ip = get_source_address(remote_ip)
    machine = get_node_from_mac_or_hardware_uuid(mac, hardware_uuid)

    # Fail with no response early so no extra work is performed.
    if machine is None and arch is None and (mac or hardware_uuid):
        # PXELinux requests boot configuration in the following order:
        # 1. pxelinux.cfg/<hardware uuid>
        # 2. pxelinux.cfg/01-<mac>
        # 3. pxelinux.cfg/default-<arch>-<subarch>
        # If mac and/or hardware_uuid was given but no Node was found fail the
        # request so PXELinux will move onto the next request.
        raise BootConfigNoResponse()

    # Get all required configuration objects in a single query.
    configs = Config.objects.get_configs(
        [
            "commissioning_osystem",
            "commissioning_distro_series",
            "enable_third_party_drivers",
            "default_min_hwe_kernel",
            "default_osystem",
            "default_distro_series",
            "kernel_opts",
            "use_rack_proxy",
            "maas_internal_domain",
            "remote_syslog",
            "maas_syslog_port",
        ]
    )

    # Compute the syslog server.
    log_host, log_port = (
        local_ip,
        (
            configs["maas_syslog_port"]
            if configs["maas_syslog_port"]
            else RSYSLOG_PORT
        ),
    )
    if configs["remote_syslog"]:
        log_host, log_port = splithost(configs["remote_syslog"])
        if log_port is None:
            log_port = 514  # Fallback to default UDP syslog port.

    # XXX: Instead of updating the machine directly, we should store the
    # information and update the machine later. The current code doesn't
    # work when you first boot a machine that has IPMI configured, since
    # at the first boot you don't have enough information to identify
    # the machine. If we had this information below in the database, we
    # could grab it when processing the commissioning results.
    # See bug #1899486 for more information.
    if machine is not None:
        # Update the last interface, last access cluster IP address, and
        # the last used BIOS boot method.
        if machine.boot_cluster_ip != local_ip:
            machine.boot_cluster_ip = local_ip

        if machine.bios_boot_method != bios_boot_method:
            machine.bios_boot_method = bios_boot_method

        try:
            machine.boot_interface = machine.current_config.interface_set.get(
                type=INTERFACE_TYPE.PHYSICAL, mac_address=mac
            )
        except ObjectDoesNotExist:
            # MAC is unknown or wasn't sent. Determine the boot_interface using
            # the boot_cluster_ip.
            subnet = Subnet.objects.get_best_subnet_for_ip(local_ip)
            boot_vlan = getattr(machine.boot_interface, "vlan", None)
            if subnet and subnet.vlan != boot_vlan:
                # This might choose the wrong interface, but we don't
                # have enough information to decide which interface is
                # the boot one.
                machine.boot_interface = (
                    machine.current_config.interface_set.filter(
                        vlan=subnet.vlan
                    ).first()
                )
        else:
            # Update the VLAN of the boot interface to be the same VLAN for the
            # interface on the rack controller that the machine communicated
            # with, unless the VLAN is being relayed.
            rack_interface = (
                rack_controller.current_config.interface_set.filter(
                    ip_addresses__ip=local_ip
                )
                .select_related("vlan")
                .first()
            )
            if (
                rack_interface is not None
                and machine.boot_interface.vlan_id != rack_interface.vlan_id
            ):
                # Rack controller and machine is not on the same VLAN, with
                # DHCP relay this is possible. Lets ensure that the VLAN on the
                # interface is setup to relay through the identified VLAN.
                if not VLAN.objects.filter(
                    id=machine.boot_interface.vlan_id,
                    relay_vlan=rack_interface.vlan_id,
                ).exists():
                    # DHCP relay is not being performed for that VLAN. Set the
                    # VLAN to the VLAN of the rack controller.
                    machine.boot_interface.vlan = rack_interface.vlan
                    machine.boot_interface.save()

        # Reset the machine's status_expires whenever the boot_config is called
        # on a known machine. This allows a machine to take up to the maximum
        # timeout status to POST.
        machine.reset_status_expires()

        # Does nothing if the machine hasn't changed.
        machine.save()

        arch, subarch = machine.split_arch()
        if configs["use_rack_proxy"]:
            preseed_url = compose_preseed_url(
                machine,
                base_url=get_base_url_for_local_ip(
                    local_ip, configs["maas_internal_domain"]
                ),
            )
        else:
            preseed_url = compose_preseed_url(
                machine,
                base_url=rack_controller.url,
                default_region_ip=region_ip,
            )
        hostname = machine.hostname
        domain = machine.domain.name
        purpose = machine.get_boot_purpose()

        # Ephemeral deployments will have 'local' boot
        # purpose on power cycles.  Set purpose back to
        # 'xinstall' so that the system can be re-deployed.
        if purpose == "local" and machine.ephemeral_deployment:
            purpose = "xinstall"

        # Early out if the machine is booting local.
        if purpose == "local":
            if machine.is_device:
                # Log that we are setting to local boot for a device.
                maaslog.warning(
                    "Device %s with MAC address %s is PXE booting; "
                    "instructing the device to boot locally."
                    % (machine.hostname, mac)
                )
                # Set the purpose to 'local-device' so we can log a message
                # on the rack.
                purpose = "local-device"

            return {
                "system_id": machine.system_id,
                "arch": arch,
                "subarch": subarch,
                "osystem": machine.osystem,
                "release": machine.distro_series,
                "kernel": "",
                "initrd": "",
                "boot_dtb": "",
                "purpose": purpose,
                "hostname": hostname,
                "domain": domain,
                "preseed_url": preseed_url,
                "fs_host": local_ip,
                "log_host": log_host,
                "log_port": log_port,
                "extra_opts": "",
                "http_boot": True,
            }

        # Log the request into the event log for that machine.
        if (
            machine.status
            in [NODE_STATUS.ENTERING_RESCUE_MODE, NODE_STATUS.RESCUE_MODE]
            and purpose == "commissioning"
        ):
            event_log_pxe_request(machine, "rescue")
        else:
            event_log_pxe_request(machine, purpose)

        osystem, series, subarch = get_boot_config_for_machine(
            machine, configs, purpose
        )

        extra_kernel_opts = machine.get_effective_kernel_options(
            default_kernel_opts=configs["kernel_opts"]
        )

        # Add any extra options from a third party driver.
        use_driver = configs["enable_third_party_drivers"]
        if use_driver:
            driver = get_third_party_driver(machine, series=series)
            driver_kernel_opts = driver.get("kernel_opts", "")

            extra_kernel_opts += f" {driver_kernel_opts}"

        extra_kernel_opts.strip()

        kparams = BootResource.objects.get_kparams_for_node(
            machine,
            default_osystem=configs["default_osystem"],
            default_distro_series=configs["default_distro_series"],
        )
        extra_kernel_opts = merge_kparams_with_extra(
            kparams, extra_kernel_opts
        )
    else:
        purpose = "commissioning"  # enlistment
        if configs["use_rack_proxy"]:
            preseed_url = compose_enlistment_preseed_url(
                base_url=get_base_url_for_local_ip(
                    local_ip, configs["maas_internal_domain"]
                )
            )
        else:
            preseed_url = compose_enlistment_preseed_url(
                rack_controller=rack_controller, default_region_ip=region_ip
            )
        hostname = "maas-enlist"
        domain = "local"
        osystem = configs["commissioning_osystem"]
        series = configs["commissioning_distro_series"]
        min_hwe_kernel = configs["default_min_hwe_kernel"]

        # When no architecture is defined for the enlisting machine select
        # the best boot resource for the operating system and series. If
        # none exists fallback to the default architecture. LP #1181334
        if arch is None:
            resource = BootResource.objects.get_default_commissioning_resource(
                osystem, series
            )
            if resource is None:
                arch = DEFAULT_ARCH
            else:
                arch, _ = resource.split_arch()
        # The subarch defines what kernel is booted. With MAAS 2.1 this changed
        # from hwe-<letter> to hwe-<version> or ga-<version>. Validation
        # converts between the two formats to make sure a bootable subarch is
        # selected.
        if subarch is None:
            min_hwe_kernel = get_working_kernel(
                None, min_hwe_kernel, "%s/generic" % arch, osystem, series
            )
        else:
            min_hwe_kernel = get_working_kernel(
                None,
                min_hwe_kernel,
                f"{arch}/{subarch}",
                osystem,
                series,
            )
        # If no hwe_kernel was found set the subarch to the default, 'generic.'
        if min_hwe_kernel is None:
            subarch = "generic"
        else:
            subarch = min_hwe_kernel

        # Global kernel options for enlistment.
        extra_kernel_opts = configs["kernel_opts"]

    boot_purpose = get_final_boot_purpose(machine, arch, purpose)
    kernel, initrd, boot_dtb = get_boot_filenames(
        arch,
        subarch,
        osystem,
        series,
        commissioning_osystem=configs["commissioning_osystem"],
        commissioning_distro_series=configs["commissioning_distro_series"],
    )

    # Return the params to the rack controller. Include the system_id only
    # if the machine was known.
    params = {
        "arch": arch,
        "subarch": subarch,
        "osystem": osystem,
        "release": series,
        "kernel": kernel,
        "initrd": initrd,
        "boot_dtb": boot_dtb,
        "purpose": boot_purpose,
        "hostname": hostname,
        "domain": domain,
        "preseed_url": preseed_url,
        "fs_host": local_ip,
        "log_host": log_host,
        "log_port": log_port,
        "extra_opts": "" if extra_kernel_opts is None else extra_kernel_opts,
        # As of MAAS 2.4 only HTTP boot is supported. This ensures MAAS 2.3
        # rack controllers use HTTP boot as well.
        "http_boot": True,
    }
    if machine is not None:
        params["system_id"] = machine.system_id
    return params
