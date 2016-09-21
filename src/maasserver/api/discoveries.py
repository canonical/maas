# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `Discovery`."""

__all__ = [
    'DiscoveryHandler',
    'DiscoveriesHandler',
    ]

from textwrap import dedent

from django.http.response import (
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from formencode.validators import StringBool
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import get_optional_param
from maasserver.enum import NODE_PERMISSION
from maasserver.models import Discovery
from piston3.utils import rc


DISPLAYED_DISCOVERY_FIELDS = (
    'discovery_id',
    'ip',
    'mac_address',
    'mac_organization',
    'last_seen',
    'hostname',
    'fabric_name',
    'vid',
    'observer',
)
from maasserver.clusterrpc.utils import (
    call_racks_synchronously,
    RPCResults,
)
from provisioningserver.rpc import cluster


class DiscoveryHandler(OperationsHandler):
    """Read or delete an observed discovery."""
    api_doc_section_name = "Discovery"
    # This is a view-backed, read-only API.
    create = delete = update = None
    fields = DISPLAYED_DISCOVERY_FIELDS
    model = Discovery

    @classmethod
    def resource_uri(cls, discovery=None):
        # See the comment in NodeHandler.resource_uri.
        discovery_id = "discovery_id"
        if discovery is not None:
            # discovery_id = quote_url(discovery.discovery_id)
            discovery_id = discovery.discovery_id
        return ('discovery_handler', (discovery_id,))

    def read(self, request, **kwargs):
        discovery_id = kwargs.get('discovery_id', None)
        discovery = Discovery.objects.get_discovery_or_404(discovery_id)
        return discovery

    @classmethod
    def observer(cls, discovery):
        return {
            'system_id': discovery.observer_system_id,
            'hostname': discovery.observer_hostname,
            'interface_id': discovery.observer_interface_id,
            'interface_name': discovery.observer_interface_name,
        }


class DiscoveriesHandler(OperationsHandler):
    """Query observed discoveries."""
    api_doc_section_name = "Discoveries"
    # This is a view-backed, read-only API.
    create = update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('discoveries_handler', [])

    def read(self, request, **kwargs):
        """Lists all the devices MAAS has discovered.

        Discoveries are listed in the order they were last observed on the
        network (most recent first).
        """
        return Discovery.objects.all().order_by("-last_seen")

    @operation(idempotent=True)
    def by_unknown_mac(self, request, **kwargs):
        """Lists all discovered devices which have an unknown IP address.

        Filters the list of discovered devices by excluding any discoveries
        where an interface known to MAAS is configured with MAC address of the
        discovery.

        Discoveries are listed in the order they were last observed on the
        network (most recent first).
        """
        return Discovery.objects.by_unknown_mac().order_by("-last_seen")

    @operation(idempotent=True)
    def by_unknown_ip(self, request, **kwargs):
        """Lists all discovered devices which have an unknown IP address.

        Filters the list of discovered devices by excluding any discoveries
        where a known MAAS node is configured with the IP address of the
        discovery, or has been observed using it after it was assigned by
        a MAAS-managed DHCP server.

        Discoveries are listed in the order they were last observed on the
        network (most recent first).
        """
        return Discovery.objects.by_unknown_ip().order_by("-last_seen")

    @operation(idempotent=True)
    def by_unknown_ip_and_mac(self, request, **kwargs):
        """Lists all discovered devices which are completely unknown to MAAS.

        Filters the list of discovered devices by excluding any discoveries
        where a known MAAS node is configured with either the MAC address or
        the IP address of the discovery.

        Discoveries are listed in the order they were last observed on the
        network (most recent first).
        """
        return Discovery.objects.by_unknown_ip_and_mac().order_by("-last_seen")

    @operation(idempotent=False)
    def clear(self, request, **kwargs):
        """Deletes all discovered neighbours and/or mDNS entries.

        :param mdns: if True, deletes all mDNS entries.
        :param neighbours: if True, deletes all neighbour entries.
        :param all: if True, deletes all discovery data.
        """
        all = get_optional_param(
            request.POST, 'all', default=False, validator=StringBool)
        mdns = get_optional_param(
            request.POST, 'mdns', default=False, validator=StringBool)
        neighbours = get_optional_param(
            request.POST, 'neighbours', default=False, validator=StringBool)

        if not request.user.has_perm(NODE_PERMISSION.ADMIN, Discovery):
            response = HttpResponseForbidden(
                content_type='text/plain',
                content="Must be an administrator to clear discovery entries.")
            return response
        if True not in (mdns, neighbours, all):
            content = dedent("""\
                Bad request: could not determine what data to clear.
                Must specify mdns=True, neighbours=True, or all=True.""")
            response = HttpResponseBadRequest(
                content_type='text/plain', content=content)
            return response
        Discovery.objects.clear(
            user=request.user, all=all, mdns=mdns, neighbours=neighbours)
        return rc.DELETED

    @operation(idempotent=False)
    def scan(self, request, **kwargs):
        """Immediately run a neighbour discovery scan on all rack networks.

        This command causes each connected rack controller to execute the
        'maas-rack scan-network' command, which will scan all CIDRs configured
        on the rack controller using 'nmap' (if it is installed) or 'ping'.

        Network discovery must not be set to 'disabled' for this command to be
        useful.

        Scanning will be started in the background, and could take a long time
        on rack controllers that do not have 'nmap' installed and are connected
        to large networks.

        If the call is a success, this method will return a dictionary of
        results as follows:

        result: A human-readable string summarizing the results.
        scan_attempted_on: A list of rack 'system_id' values where a scan
        was attempted. (That is, an RPC connection was successful and a
        subsequent call was intended.)

        failed_to_connect_to: A list of rack 'system_id' values where the RPC
        connection failed.

        scan_started_on: A list of rack 'system_id' values where a scan was
        successfully started.

        scan_already_in_progress_on: A list of rack 'system_id' values where
        a scan was attempted, but failed because a scan was already in
        progress.

        rpc_call_timed_out_on: A list of rack 'system_id' values where the
        RPC connection was made, but the call timed out before a ten second
        timeout elapsed.
        """
        return scan_all_rack_networks()


def interpret_scan_all_rack_networks_rpc_results(
        rpc_results: RPCResults) -> str:
    """Return a human-readable string with the results of `ScanAllNetworks`."""
    if len(rpc_results.available) == 0:
        result = (
            "Unable to initiate network scanning on any rack controller. "
            "Verify that the rack controllers are started and have "
            "connected to the region.")
    elif len(rpc_results.unavailable) > 0:
        result = (
            "Scanning could not be started on %d rack controller(s). "
            "Verify that all rack controllers are connected to the "
            "region." % len(rpc_results.unavailable))
    else:
        result = "Scanning is in-progress on all rack controllers."
    return result


def scan_all_rack_networks() -> dict:
    """Call each rack and instruct it to scan all attached networks.

    Interprets the results and returns a dict with the following keys:
        result: A human-readable string summarizing the results.
        scan_attempted_on: A list of rack `system_id` values where a scan
            was attempted. (That is, an RPC connection was successful and
            a subsequent call was intended.)
        failed_to_connect_to: A list of rack `system_id values where the
            RPC connection failed.
        scan_started_on: A list of rack `system_id` values where a scan
            was successfully started.
        scan_already_in_progress_on: A list of rack `system_id` values where
            a scan was attempted, but failed because a scan was already in
            progress.
        rpc_call_timed_out_on: A list of rack `system_id` values where the
            RPC connection was made, but the call timed out before the
            ten second timeout elapsed.

    This function is intended to be used directly by the API and websocket
    layers, so must return a dict that is safe to encode to JSON.

    :return: dict
    """
    rpc_results = call_racks_synchronously(cluster.ScanAllNetworks)
    result = interpret_scan_all_rack_networks_rpc_results(rpc_results)
    # WARNING: This method returns a dictionary which is directly used in the
    # result of a MAAS API call. Keys returned in this dictionary cannot be
    # renamed or removed, and (values cannot be repurposed) without breaking
    # API backward compatibility.
    return {
        "result": result,
        "scan_started_on":
            [rack.system_id for rack in rpc_results.success],
        # Note that failure can only mean one thing: that the scan is
        # already in progress.
        "scan_already_in_progress_on":
            [rack.system_id for rack in rpc_results.failed],
        "scan_attempted_on":
            [rack.system_id for rack in rpc_results.available],
        "failed_to_connect_to":
            [rack.system_id for rack in rpc_results.unavailable],
        # This is very unlikely to happen, but it's here just in case.
        "rpc_call_timed_out_on":
            [rack.system_id for rack in rpc_results.timeout]
    }
