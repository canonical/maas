from functools import partial

from django.core.exceptions import ObjectDoesNotExist
from tftp.backend import FilesystemSynchronousBackend
from tftp.errors import BackendError, FileNotFound
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks, maybeDeferred, returnValue
from twisted.internet.task import deferLater
from twisted.python.filepath import FilePath

from maasserver.compose_preseed import RSYSLOG_PORT
from maasserver.config import RegionConfiguration
from maasserver.enum import INTERFACE_TYPE
from maasserver.events import send_node_event_ip_address
from maasserver.models import (
    Config,
    RackController,
    RegionController,
    Subnet,
    VLAN,
)
from maasserver.preseed import compose_preseed_url
from maasserver.rpc import nodes
from maasserver.rpc.boot import (
    get_base_url_for_local_ip,
    get_node_from_mac_or_hardware_uuid,
)
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from provisioningserver.boot import BootMethodRegistry
from provisioningserver.drivers import ArchitectureRegistry
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.events import EVENT_TYPES
from provisioningserver.kernel_opts import KernelParameters
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.rackdservices import tftp as rack_tftp
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from provisioningserver.utils import network, tftp, typed
from provisioningserver.utils.tftp import TFTPPath
from provisioningserver.utils.twisted import deferred, synchronous
from provisioningserver.utils.url import splithost

maaslog = get_maas_logger("tftp")
log = LegacyLogger()


def log_request(file_name, clock=reactor):
    if isinstance(file_name, bytes):
        file_name = file_name.decode("ascii", "replace")
    # Log to the regular log.
    remote_host, _ = tftp.get_remote_address()
    log.info(
        "{file_name} requested by {remote_host}",
        file_name=file_name,
        remote_host=remote_host,
    )
    # Log to the node event log.
    d = deferLater(
        clock,
        0,
        send_node_event_ip_address,
        event_type=EVENT_TYPES.NODE_TFTP_REQUEST,
        ip_address=remote_host,
        description=file_name,
    )
    d.addErrback(log.err, "Logging TFTP request failed.")


@synchronous
@transactional
def get_boot_configs(
    local_ip,
    remote_ip,
    arch=None,
    subarch=None,
    mac=None,
    hardware_uuid=None,
    bios_boot_method=None,
):
    machine = get_node_from_mac_or_hardware_uuid(mac, hardware_uuid)
    current_region_controller = (
        RegionController.objects.get_running_controller()
    )

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
            machine.boot_interface = machine.interface_set.get(
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
                machine.boot_interface = machine.interface_set.filter(
                    vlan=subnet.vlan
                ).first()
        else:
            # Update the VLAN of the boot interface to be the same VLAN for the
            # interface on the rack controller that the machine communicated
            # with, unless the VLAN is being relayed.
            rack_interface = None
            # TODO proxy needs to pass back enough info to query for the rack controller proxying
            # (
            #    rack_controller.interface_set.filter(ip_addresses__ip=local_ip)
            #    .select_related("vlan")
            #    .first()
            # )
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
                base_url=current_region_controller.url,
                default_region_ip=local_ip,
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


@synchronous
def get_servers(system_id):
    rack_controller = RackController.objects.get(system_id=system_id)
    region_controllers = RegionController.objects.all()

    with RegionConfiguration.open() as config:
        tftp_port = config.tftp_port

    servers = []

    for region_controller in region_controllers:
        for iface in region_controller.interface_set.all():
            rack_iface = rack_controller.interface_set.filter(
                vlan=iface.vlan
            )  # just need one match
            if rack_iface is not None:
                for link in iface.get_links():
                    servers.append(
                        link.get("ip_address") + ":" + str(tftp_port)
                    )
    return servers


class RegionTFTPBackend(FilesystemSynchronousBackend):
    def __init__(self, base_path):
        """
        :param base_path: The root directory for this TFTP server.
        """
        if not isinstance(base_path, FilePath):
            base_path = FilePath(base_path)
        super().__init__(base_path, can_read=True, can_write=False)

    @inlineCallbacks
    @typed
    def get_boot_method(self, file_name: TFTPPath):
        """Finds the correct boot method."""
        for _, method in BootMethodRegistry:
            params = yield maybeDeferred(method.match_path, self, file_name)
            if params is not None:
                params["bios_boot_method"] = method.bios_boot_method
                returnValue((method, params))
        returnValue((None, None))

    def get_boot_image(self, params, remote_ip):
        """Get the boot image for the params on this rack controller.

        Calls `MarkNodeFailed` for the machine if its a known machine.
        """
        is_ephemeral = False
        try:
            osystem_obj = OperatingSystemRegistry.get_item(
                params["osystem"], default=None
            )
            purposes = osystem_obj.get_boot_image_purposes(
                params["arch"],
                params["subarch"],
                params.get("release", ""),
                params.get("label", ""),
            )
            if "ephemeral" in purposes:
                is_ephemeral = True
        except Exception:
            pass

        # Check to see if the we are PXE booting a device.
        if params["purpose"] == "local-device":
            mac = network.find_mac_via_arp(remote_ip)
            log.info(
                "Device %s with MAC address %s is PXE booting; "
                "instructing the device to boot locally."
                % (params["hostname"], mac)
            )

        system_id = params.pop("system_id", None)
        if params["purpose"] == "local" and not is_ephemeral:
            # Local purpose doesn't use a boot image so just set the label
            # to "local".
            params["label"] = "local"
            return params
        else:
            if params["purpose"] == "local" and is_ephemeral:
                params["purpose"] = "ephemeral"
            boot_image = rack_tftp.get_boot_image(params)
            if boot_image is None:
                # No matching boot image.
                description = "Missing boot image %s/%s/%s/%s." % (
                    params["osystem"],
                    params["arch"],
                    params["subarch"],
                    params["release"],
                )
                # Call MarkNodeFailed if this was a known machine.
                if system_id is not None:
                    d = deferToDatabase(
                        nodes.mark_node_failed,
                        system_id,
                        description,
                    )
                    d.addErrback(
                        log.err,
                        "Failed to mark machine failed: %s" % description,
                    )
                else:
                    maaslog.error(
                        "Enlistment failed to boot %s; missing required boot "
                        "image %s/%s/%s/%s."
                        % (
                            remote_ip,
                            params["osystem"],
                            params["arch"],
                            params["subarch"],
                            params["release"],
                        )
                    )
                params["label"] = "no-such-image"
            else:
                params["label"] = boot_image["label"]
            return params

    @deferred
    def get_kernel_params(self, params):
        """Return kernel parameters obtained from the API.

        :param params: Parameters so far obtained, typically from the file
            path requested.
        :return: A `KernelParameters` instance.
        """
        # Extract from params only those arguments that GetBootConfig cares
        # about; params is a context-like object and other stuff (too much?)
        # gets in there.
        arguments = (
            "system_id",
            "local_ip",
            "remote_ip",
            "arch",
            "subarch",
            "mac",
            "hardware_uuid",
            "bios_boot_method",
        )
        params = {name: params[name] for name in arguments if name in params}

        d = deferToDatabase(get_boot_configs(**params))
        d.addCallback(self.get_boot_image, params["remote_ip"])
        d.addCallback(lambda data: KernelParameters(**data))
        return d

    @deferred
    def get_boot_method_reader(self, boot_method, params):
        """Return an `IReader` for a boot method.

        :param boot_method: Boot method that is generating the config
        :param params: Parameters so far obtained, typically from the file
            path requested.
        """

        def generate(kernel_params):
            return boot_method.get_reader(
                self, kernel_params=kernel_params, **params
            )

        return self.get_kernel_params(params).addCallback(generate)

    @staticmethod
    def no_response_errback(failure, file_name):
        failure.trap(BootConfigNoResponse)
        # Convert to a TFTP file not found.
        raise FileNotFound(file_name)

    @deferred
    @typed
    def handle_boot_method(self, file_name: TFTPPath, protocol: str, result):
        boot_method, params = result
        if boot_method is None:
            return super().get_reader(file_name)

        # Map pxe namespace architecture names to MAAS's.
        arch = params.get("arch")
        if arch is not None:
            maasarch = ArchitectureRegistry.get_by_pxealias(arch)
            if maasarch is not None:
                params["arch"] = maasarch.name.split("/")[0]

        # Send the local and remote endpoint addresses.
        local_host, local_port = tftp.get_local_address()
        params["local_ip"] = local_host
        remote_host, remote_port = tftp.get_remote_address()
        params["remote_ip"] = remote_host
        params["protocol"] = protocol if protocol else "tftp"
        d = self.get_boot_method_reader(boot_method, params)
        return d

    @staticmethod
    def all_is_lost_errback(failure):
        if failure.check(BackendError):
            # This failure is something that the TFTP server knows how to deal
            # with, so pass it through.
            return failure
        else:
            # Something broke badly; record it.
            log.err(failure, "TFTP back-end failed.")
            # Don't keep people waiting; tell them something broke right now.
            raise BackendError(failure.getErrorMessage())

    @deferred
    @typed
    def get_reader(
        self,
        file_name: TFTPPath,
        skip_logging: bool = False,
        protocol: str = None,
    ):
        """See `IBackend.get_reader()`.

        If `file_name` matches a boot method then the response is obtained
        from that boot method. Otherwise the filesystem is used to service
        the response.
        """
        # It is possible for a client to request the file with '\' instead
        # of '/', example being 'bootx64.efi'. Convert all '\' to '/' to be
        # unix compatiable.
        file_name = file_name.replace(b"\\", b"/")
        if not skip_logging:
            # HTTP handler will call with `skip_logging` set to True so that
            # 2 log messages are not created.
            log_request(file_name)
        d = self.get_boot_method(file_name)
        d.addCallback(partial(self.handle_boot_method, file_name, protocol))
        d.addErrback(self.no_response_errback, file_name)
        d.addErrback(self.all_is_lost_errback)
        return d


class RegionTFTPService(rack_tftp.TFTPService):
    def __init__(self, resource_root, port):
        super(RegionTFTPService, self).__init__(resource_root, port, None)
        self.backend = RegionTFTPBackend(resource_root)
