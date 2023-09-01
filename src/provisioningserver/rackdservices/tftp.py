# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Twisted Application Plugin for the MAAS TFTP server."""


from functools import partial
from socket import AF_INET, AF_INET6
from time import time

from netaddr import IPAddress
from tftp.backend import FilesystemSynchronousBackend
from tftp.errors import BackendError, FileNotFound
from tftp.protocol import TFTP
from twisted.application import internet
from twisted.application.service import MultiService
from twisted.internet import reactor, udp
from twisted.internet.abstract import isIPv6Address
from twisted.internet.address import IPv4Address, IPv6Address
from twisted.internet.defer import (
    inlineCallbacks,
    maybeDeferred,
    returnValue,
    succeed,
)
from twisted.internet.task import deferLater
from twisted.python.filepath import FilePath

from provisioningserver.boot import BootMethodRegistry
from provisioningserver.drivers import ArchitectureRegistry
from provisioningserver.events import EVENT_TYPES, send_node_event_ip_address
from provisioningserver.kernel_opts import KernelParameters
from provisioningserver.logger import get_maas_logger, LegacyLogger
from provisioningserver.prometheus.metrics import PROMETHEUS_METRICS
from provisioningserver.rpc.boot_images import list_boot_images
from provisioningserver.rpc.exceptions import BootConfigNoResponse
from provisioningserver.rpc.region import GetBootConfig, MarkNodeFailed
from provisioningserver.utils import network, tftp
from provisioningserver.utils.network import get_all_interface_addresses
from provisioningserver.utils.tftp import TFTPPath
from provisioningserver.utils.twisted import deferred, RPCFetcher

maaslog = get_maas_logger("tftp")
log = LegacyLogger()


def get_boot_image(params):
    """Get the boot image for the params on this rack controller."""
    # Match on purpose; enlist uses the commissioning purpose.
    purpose = params["purpose"]
    if purpose == "enlist":
        purpose = "commissioning"

    # Get the matching boot images, minus subarchitecture.
    boot_images = list_boot_images()
    boot_images = [
        image
        for image in boot_images
        if (
            image["osystem"] == params["osystem"]
            and image["release"] == params["release"]
            and image["architecture"] == params["arch"]
            and image["purpose"] == purpose
        )
    ]

    # See if exact subarchitecture match.
    for image in boot_images:
        if image["subarchitecture"] == params["subarch"]:
            return image

    # Not exact match check if subarchitecture is in the supported
    # subarchitectures list.
    for image in boot_images:
        subarches = image.get("supported_subarches", "")
        subarches = subarches.split(",")
        if params["subarch"] in subarches:
            return image

    # No matching boot image was found.
    return None


def log_request(file_name, clock=reactor):
    """Log a TFTP request.

    This will be logged to the regular log, and also to the node event log at
    a later iteration of the `clock` so as to not delay the task currently in
    progress.
    """
    # If the file name is a byte string, decode it as ASCII, replacing
    # non-ASCII characters, so that we have at least something to log.
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


class TFTPBackend(FilesystemSynchronousBackend):
    """A partially dynamic read-only TFTP server.

    Static files such as kernels and initrds, as well as any non-MAAS files
    that the system may already be set up to serve, are served up normally.
    But PXE configurations are generated on the fly.

    When a PXE configuration file is requested, the server asynchronously
    requests the appropriate parameters from the API (at a configurable
    "generator URL") and generates a config file based on those.

    The regular expressions `re_config_file` and `re_mac_address` specify
    which files the server generates on the fly.  Any other requests are
    passed on to the filesystem.

    Passing requests on to the API must be done very selectively, because
    failures cause the boot process to halt. This is why the expression for
    matching the MAC address is so narrowly defined: PXELINUX attempts to
    fetch files at many similar paths which must not be passed on.
    """

    def __init__(self, base_path, client_service):
        """
        :param base_path: The root directory for this TFTP server.
        :param client_service: The RPC client service for the rack controller.
        """
        if not isinstance(base_path, FilePath):
            base_path = FilePath(base_path)
        super().__init__(base_path, can_read=True, can_write=False)
        self.client_to_remote = {}
        self.client_service = client_service
        self.fetcher = RPCFetcher()

    def _get_new_client_for_remote(self, remote_ip):
        """Return a new client for the `remote_ip`.

        Don't use directly called from `get_client_for`.
        """

        def store_client(client):
            self.client_to_remote[remote_ip] = client
            return client

        d = self.client_service.getClientNow()
        d.addCallback(store_client)
        return d

    def get_client_for(self, params):
        """Always gets the same client based on `params`.

        This is done so that all TFTP requests from the same remote client go
        to the same regiond process. `RPCFetcher` only duplciate on the client
        and arguments, so if the client is not the same the duplicate effort
        is not consolidated.
        """
        remote_ip = params.get("remote_ip")
        if remote_ip:
            client = self.client_to_remote.get(remote_ip, None)
            if client is None:
                # Get a new client for the remote_ip.
                return self._get_new_client_for_remote(remote_ip)
            else:
                # Check that the existing client is still valid.
                clients = self.client_service.getAllClients()
                if client in clients:
                    return succeed(client)
                else:
                    del self.client_to_remote[remote_ip]
                    return self._get_new_client_for_remote(remote_ip)
        else:
            return self.client_service.getClientNow()

    @inlineCallbacks
    def get_boot_method(self, file_name: TFTPPath):
        """Finds the correct boot method."""
        for _, method in BootMethodRegistry:
            params = yield maybeDeferred(method.match_path, self, file_name)
            if params is not None:
                params["bios_boot_method"] = method.bios_boot_method
                returnValue((method, params))
        returnValue((None, None))

    def get_boot_image(self, params, client, remote_ip):
        """Get the boot image for the params on this rack controller.

        Calls `MarkNodeFailed` for the machine if its a known machine.
        """

        # Check to see if the we are PXE booting a device.
        if params["purpose"] == "local-device":
            mac = network.find_mac_via_arp(remote_ip)
            log.info(
                "Device %s with MAC address %s is PXE booting; "
                "instructing the device to boot locally."
                % (params["hostname"], mac)
            )
            # Set purpose back to local now that we have the message logged.
            params["purpose"] = "local"

        system_id = params.pop("system_id", None)
        if params["purpose"] == "local":
            # Local purpose doesn't use a boot image so just set the label
            # to "local".
            params["label"] = "local"
            return params
        else:
            boot_image = get_boot_image(params)
            if boot_image is None:
                # No matching boot image.
                description = "Missing boot image {}/{}/{}/{}.".format(
                    params["osystem"],
                    params["arch"],
                    params["subarch"],
                    params["release"],
                )
                # Call MarkNodeFailed if this was a known machine.
                if system_id is not None:
                    d = client(
                        MarkNodeFailed,
                        system_id=system_id,
                        error_description=description,
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
            name.decode("ascii") for name, _ in GetBootConfig.arguments
        )
        params = {name: params[name] for name in arguments if name in params}

        def fetch(client, params):
            params["system_id"] = client.localIdent
            d = self.fetcher(client, GetBootConfig, **params)
            d.addCallback(self.get_boot_image, client, params["remote_ip"])
            d.addCallback(lambda data: KernelParameters(**data))
            return d

        d = self.get_client_for(params)
        d.addCallback(fetch, params)
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


class Port(udp.Port):
    """A :py:class:`udp.Port` that groks IPv6."""

    # This must be set by call sites.
    addressFamily = None

    def getHost(self):
        """See :py:meth:`twisted.internet.udp.Port.getHost`."""
        host, port = self.socket.getsockname()[:2]
        addr_type = IPv6Address if isIPv6Address(host) else IPv4Address
        return addr_type("UDP", host, port)


class UDPServer(internet.UDPServer):
    """A :py:class:`~internet.UDPServer` that groks IPv6.

    This creates the port directly instead of using the reactor's
    ``listenUDP`` method so that we can do a switcharoo to our own
    IPv6-enabled port implementation.
    """

    def _getPort(self):
        """See :py:meth:`twisted.application.internet.UDPServer._getPort`."""
        return self._listenUDP(*self.args, **self.kwargs)

    def _listenUDP(self, port, protocol, interface="", maxPacketSize=8192):
        """See :py:meth:`twisted.internet.reactor.listenUDP`."""
        p = Port(port, protocol, interface, maxPacketSize)
        p.addressFamily = AF_INET6 if isIPv6Address(interface) else AF_INET
        p.startListening()
        return p


def track_tftp_latency(
    func, start_time, filename, prometheus_metrics=PROMETHEUS_METRICS
):
    """Wraps a function and tracks TFTP transfer latency."""

    def wrapped():
        result = func()
        latency = time() - start_time
        prometheus_metrics.update(
            "maas_tftp_file_transfer_latency",
            "observe",
            labels={"filename": filename},
            value=latency,
        )
        return result

    return wrapped


class TransferTimeTrackingTFTP(TFTP):
    @inlineCallbacks
    def _startSession(
        self, datagram, addr, mode, prometheus_metrics=PROMETHEUS_METRICS
    ):
        session = yield super()._startSession(datagram, addr, mode)
        stream_session = getattr(session, "session", None)
        # replace the standard cancel() method with one that tracks
        # transfer time
        if stream_session is not None:
            filename = self._clean_filename(datagram)
            start_time = time()
            stream_session.cancel = track_tftp_latency(
                stream_session.cancel,
                start_time,
                filename,
                prometheus_metrics=prometheus_metrics,
            )
        returnValue(session)

    def _clean_filename(self, datagram):
        filename = datagram.filename.decode("ascii")
        filename = filename.replace("\\", "/")  # normalize Windows paths
        filename = filename.lstrip("/")
        if "pxelinux.cfg/" in filename:
            return "pxelinux.cfg"
        if filename.startswith("grub/grub.cfg-"):
            return "grub/grub.cfg"

        return filename


class TFTPService(MultiService):
    """An umbrella service representing a set of running TFTP servers.

    Creates a UDP server individually for each discovered network
    interface, so that we can detect the interface via which we have
    received a datagram.

    It then periodically updates the servers running in case there's a
    change to the host machine's network configuration.

    :ivar backend: The :class:`TFTPBackend` being used to service TFTP
        requests.

    :ivar port: The port on which each server is started.

    :ivar refresher: A :class:`TimerService` that calls
        ``updateServers`` periodically.

    """

    def __init__(self, resource_root, port, client_service):
        """
        :param resource_root: The root directory for this TFTP server.
        :param port: The port on which each server should be started.
        :param client_service: The RPC client service for the rack controller.
        """
        super().__init__()
        self.backend = TFTPBackend(resource_root, client_service)
        self.port = port
        # Establish a periodic call to self.updateServers() every 45
        # seconds, so that this service eventually converges on truth.
        # TimerService ensures that a call is made to it's target
        # function immediately as it's started, so there's no need to
        # call updateServers() from here.
        self.refresher = internet.TimerService(45, self.updateServers)
        self.refresher.setName("refresher")
        self.refresher.setServiceParent(self)

    def getServers(self):
        """Return a set of all configured servers.

        :rtype: :class:`set` of :class:`internet.UDPServer`
        """
        return {service for service in self if service is not self.refresher}

    def updateServers(self):
        """Run a server on every interface.

        For each configured network interface this will start a TFTP
        server. If called later it will bring up servers on newly
        configured interfaces and bring down servers on deconfigured
        interfaces.
        """
        addrs_established = {service.name for service in self.getServers()}
        addrs_desired = set(get_all_interface_addresses())

        for address in addrs_desired - addrs_established:
            if not IPAddress(address).is_link_local():
                tftp_service = UDPServer(
                    self.port,
                    TransferTimeTrackingTFTP(self.backend),
                    interface=address,
                )
                tftp_service.setName(address)
                tftp_service.setServiceParent(self)

        for address in addrs_established - addrs_desired:
            tftp_service = self.getServiceNamed(address)
            tftp_service.disownServiceParent()
