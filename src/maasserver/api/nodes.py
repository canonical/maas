# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
)

str = None

__metaclass__ = type
__all__ = [
    "AnonNodesHandler",
    "NodeHandler",
    "NodesHandler",
    "store_node_power_parameters",
]

from base64 import b64decode
import re

import bson
import crochet
from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver import locks
from maasserver.api.logger import maaslog
from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_mandatory_param,
    get_oauth_token,
    get_optional_list,
    get_optional_param,
)
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.enum import (
    IPADDRESS_TYPE,
    NODE_PERMISSION,
    NODE_STATUS,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    NodesNotAvailable,
    NodeStateViolation,
    PowerProblem,
    StaticIPAddressExhaustion,
    Unauthorized,
)
from maasserver.fields import MAC_RE
from maasserver.forms import (
    BulkNodeActionForm,
    ClaimIPForm,
    get_node_create_form,
    get_node_edit_form,
    ReleaseIPForm,
)
from maasserver.forms_commission import CommissionForm
from maasserver.models import (
    Config,
    Interface,
    Node,
    StaticIPAddress,
)
from maasserver.models.node import RELEASABLE_STATUSES
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.node_constraint_filter_forms import AcquireNodeForm
from maasserver.rpc import getClientFor
from maasserver.storage_layouts import (
    StorageLayoutError,
    StorageLayoutForm,
    StorageLayoutMissingBootDiskError,
)
from maasserver.utils import find_nodegroup
from maasserver.utils.orm import get_first
from piston.utils import rc
from provisioningserver.drivers.power import POWER_QUERY_TIMEOUT
from provisioningserver.power.poweraction import (
    PowerActionFail,
    UnknownPowerType,
)
from provisioningserver.power.schema import UNKNOWN_POWER_TYPE
from provisioningserver.rpc.cluster import PowerQuery
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
import simplejson as json

# Node's fields exposed on the API.
DISPLAYED_NODE_FIELDS = (
    'system_id',
    'hostname',
    'owner',
    'macaddress_set',
    'pxe_mac',
    'architecture',
    'min_hwe_kernel',
    'hwe_kernel',
    'cpu_count',
    'memory',
    'swap_size',
    'storage',
    'status',
    'substatus',
    'osystem',
    'distro_series',
    'boot_type',
    'netboot',
    'power_type',
    'power_state',
    'tag_names',
    'ip_addresses',
    'routers',
    'zone',
    'disable_ipv4',
    'constraint_map',
    'boot_disk',
    'blockdevice_set',
    'physicalblockdevice_set',
    'virtualblockdevice_set',
)


def store_node_power_parameters(node, request):
    """Store power parameters in request.

    The parameters should be JSON, passed with key `power_parameters`.
    """
    power_type = request.POST.get("power_type", None)
    if power_type is None:
        return

    power_types = get_power_types([node.nodegroup])

    if power_type in power_types or power_type == UNKNOWN_POWER_TYPE:
        node.power_type = power_type
    else:
        raise MAASAPIBadRequest("Bad power_type '%s'" % power_type)

    power_parameters = request.POST.get("power_parameters", None)
    if power_parameters and not power_parameters.isspace():
        try:
            node.power_parameters = json.loads(power_parameters)
        except ValueError:
            raise MAASAPIBadRequest("Failed to parse JSON power_parameters")

    node.save()


def filtered_nodes_list_from_request(request):
    """List Nodes visible to the user, optionally filtered by criteria.

    Nodes are sorted by id (i.e. most recent last).

    :param hostname: An optional hostname. Only events relating to the node
        with the matching hostname will be returned. This can be specified
        multiple times to get events relating to more than one node.
    :param mac_address: An optional MAC address. Only events relating to the
        node owning the specified MAC address will be returned. This can be
        specified multiple times to get events relating to more than one node.
    :param id: An optional list of system ids.  Only events relating to the
        nodes with matching system ids will be returned.
    :param zone: An optional name for a physical zone. Only events relating to
        the nodes in the zone will be returned.
    :param agent_name: An optional agent name.  Only events relating to the
        nodes with matching agent names will be returned.
    """
    # Get filters from request.
    match_ids = get_optional_list(request.GET, 'id')

    match_macs = get_optional_list(request.GET, 'mac_address')
    if match_macs is not None:
        invalid_macs = [
            mac for mac in match_macs if MAC_RE.match(mac) is None]
        if len(invalid_macs) != 0:
            raise MAASAPIValidationError(
                "Invalid MAC address(es): %s" % ", ".join(invalid_macs))

    # Fetch nodes and apply filters.
    nodes = Node.nodes.get_nodes(
        request.user, NODE_PERMISSION.VIEW, ids=match_ids)
    if match_macs is not None:
        nodes = nodes.filter(interface__mac_address__in=match_macs)
    match_hostnames = get_optional_list(request.GET, 'hostname')
    if match_hostnames is not None:
        nodes = nodes.filter(hostname__in=match_hostnames)
    match_zone_name = request.GET.get('zone', None)
    if match_zone_name is not None:
        nodes = nodes.filter(zone__name=match_zone_name)
    match_agent_name = request.GET.get('agent_name', None)
    if match_agent_name is not None:
        nodes = nodes.filter(agent_name=match_agent_name)

    return nodes.order_by('id')


def get_storage_layout_params(request, required=False, extract_params=False):
    """Return and validate the storage_layout parameter."""
    form = StorageLayoutForm(required=required, data=request.data)
    if not form.is_valid():
        raise MAASAPIValidationError(form.errors)
    # The request data needs to be mutable so replace the immutable QueryDict
    # with a mutable one.
    request.data = request.data.copy()
    storage_layout = request.data.pop('storage_layout', None)
    if not storage_layout:
        storage_layout = None
    else:
        storage_layout = storage_layout[0]
    params = {}
    # Grab all the storage layout parameters.
    if extract_params:
        for key, value in request.data.items():
            if key.startswith("storage_layout_"):
                params[key.replace("storage_layout_", "")] = value
        # Remove the storage_layout_ parameters from the request.
        for key in params.keys():
            request.data.pop("storage_layout_%s" % key)
    return storage_layout, params


class NodeHandler(OperationsHandler):
    """Manage an individual Node.

    The Node is identified by its system_id.
    """
    api_doc_section_name = "Node"

    create = None  # Disable create.
    model = Node
    fields = DISPLAYED_NODE_FIELDS

    @classmethod
    def status(handler, node):
        """Backward-compatibility layer: fold deployment-related statuses.

        Before the lifecycle of a node got reworked, 'allocated' meant a lot
        of things (allocated, deploying and deployed).  This is a backward
        compatiblity layer so that clients relying on the old behavior won't
        break.
        """
        old_allocated_status_aliases = [
            NODE_STATUS.ALLOCATED, NODE_STATUS.DEPLOYING,
            NODE_STATUS.DEPLOYED, NODE_STATUS.FAILED_DEPLOYMENT]
        old_deployed_status_aliases = [
            NODE_STATUS.RELEASING, NODE_STATUS.DISK_ERASING,
            NODE_STATUS.FAILED_RELEASING, NODE_STATUS.FAILED_DISK_ERASING,
        ]
        deployed_aliases = (
            old_allocated_status_aliases + old_deployed_status_aliases)
        if node.status in deployed_aliases:
            return 6  # Old allocated status.
        else:
            return node.status

    @classmethod
    def substatus(handler, node):
        """Return the substatus of the node.

        The node's status as exposed on the API corresponds to a subset of the
        actual possible statuses.  This was done to preserve backward
        compatiblity between MAAS releases.  This 'substatus' field exposes
        all the node's possible statuses as designed after the lifecyle of a
        node got reworked.
        """
        return node.status

    # Override the 'hostname' field so that it returns the FQDN instead as
    # this is used by Juju to reach that node.
    @classmethod
    def hostname(handler, node):
        return node.fqdn

    # Override 'owner' so it emits the owner's name rather than a
    # full nested user object.
    @classmethod
    def owner(handler, node):
        if node.owner is None:
            return None
        return node.owner.username

    @classmethod
    def macaddress_set(handler, node):
        return [
            {"mac_address": "%s" % interface.mac_address}
            for interface in node.interface_set.all()
            if interface.mac_address
        ]

    @classmethod
    def pxe_mac(handler, node):
        boot_interface = node.get_boot_interface()
        if boot_interface is None:
            return None
        else:
            return {"mac_address": "%s" % boot_interface.mac_address}

    def read(self, request, system_id):
        """Read a specific Node.

        Returns 404 if the node is not found.
        """
        return Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)

    @admin_method
    def update(self, request, system_id):
        """Update a specific Node.

        :param hostname: The new hostname for this node.
        :type hostname: unicode
        :param architecture: The new architecture for this node.
        :type architecture: unicode
        :param min_hwe_kernel: A string containing the minimum kernel version
            allowed to be ran on this node.
        :type min_hwe_kernel: unicode
        :param power_type: The new power type for this node. If you use the
            default value, power_parameters will be set to the empty string.
            Available to admin users.
            See the `Power types`_ section for a list of the available power
            types.
        :type power_type: unicode
        :param power_parameters_{param1}: The new value for the 'param1'
            power parameter.  Note that this is dynamic as the available
            parameters depend on the selected value of the Node's power_type.
            For instance, if the power_type is 'ether_wake', the only valid
            parameter is 'power_address' so one would want to pass 'myaddress'
            as the value of the 'power_parameters_power_address' parameter.
            Available to admin users.
            See the `Power types`_ section for a list of the available power
            parameters for each power type.
        :type power_parameters_{param1}: unicode
        :param power_parameters_skip_check: Whether or not the new power
            parameters for this node should be checked against the expected
            power parameters for the node's power type ('true' or 'false').
            The default is 'false'.
        :type power_parameters_skip_check: unicode
        :param zone: Name of a valid physical zone in which to place this node
        :type zone: unicode
        :param swap_size: Specifies the size of the swap file, in bytes. Field
            accept K, M, G and T suffixes for values expressed respectively in
            kilobytes, megabytes, gigabytes and terabytes.
        :type swap_size: unicode
        :param boot_type: The installation type of the node. 'fastpath': use
            the default installer. 'di' use the debian installer.
            Note that using 'di' is now deprecated and will be removed in favor
            of the default installer in MAAS 1.9.
        :type boot_type: unicode

        Returns 404 if the node is node found.
        Returns 403 if the user does not have permission to update the node.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        Form = get_node_edit_form(request.user)
        form = Form(data=request.data, instance=node)

        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    def delete(self, request, system_id):
        """Delete a specific Node.

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to delete the node.
        Returns 204 if the node is successfully deleted.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        node.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, node=None):
        # This method is called by piston in two different contexts:
        # - when generating an uri template to be used in the documentation
        # (in this case, it is called with node=None).
        # - when populating the 'resource_uri' field of an object
        # returned by the API (in this case, node is a Node object).
        node_system_id = "system_id"
        if node is not None:
            node_system_id = node.system_id
        return ('node_handler', (node_system_id, ))

    @operation(idempotent=False)
    def stop(self, request, system_id):
        """Shut down a node.

        :param stop_mode: An optional power off mode. If 'soft',
            perform a soft power down if the node's power type supports
            it, otherwise perform a hard power off. For all values other
            than 'soft', and by default, perform a hard power off. A
            soft power off generally asks the OS to shutdown the system
            gracefully before powering off, while a hard power off
            occurs immediately without any warning to the OS.
        :type stop_mode: unicode
        :param comment: Optional comment for the event log.
        :type comment: unicode

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to stop the node.
        """
        stop_mode = request.POST.get('stop_mode', 'hard')
        comment = get_optional_param(request.POST, 'comment')
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        power_action_sent = node.stop(
            request.user, stop_mode=stop_mode, comment=comment)
        if power_action_sent:
            return node
        else:
            return None

    @operation(idempotent=False)
    def start(self, request, system_id):
        """Power up a node.

        :param user_data: If present, this blob of user-data to be made
            available to the nodes through the metadata service.
        :type user_data: base64-encoded unicode
        :param distro_series: If present, this parameter specifies the
            OS release the node will use.
        :type distro_series: unicode
        :param hwe_kernel: If present, this parameter specified the kernel to
            be used on the node
        :type hwe_kernel: unicode
        :param comment: Optional comment for the event log.
        :type comment: unicode

        Ideally we'd have MIME multipart and content-transfer-encoding etc.
        deal with the encapsulation of binary data, but couldn't make it work
        with the framework in reasonable time so went for a dumb, manual
        encoding instead.

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to start the node.
        Returns 503 if the start-up attempted to allocate an IP address,
        and there were no IP addresses available on the relevant cluster
        interface.
        """
        user_data = request.POST.get('user_data', None)
        series = request.POST.get('distro_series', None)
        license_key = request.POST.get('license_key', None)
        hwe_kernel = request.POST.get('hwe_kernel', None)
        comment = get_optional_param(request.POST, 'comment')

        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)

        if node.owner is None:
            raise NodeStateViolation(
                "Can't start node: it hasn't been allocated.")
        if user_data is not None:
            user_data = b64decode(user_data)
        if not node.distro_series and not series:
            series = Config.objects.get_config('default_distro_series')
        if (series, license_key, hwe_kernel) != (None, None, None):
            Form = get_node_edit_form(request.user)
            form = Form(instance=node)
            if series is not None:
                form.set_distro_series(series=series)
            if license_key is not None:
                form.set_license_key(license_key=license_key)
            if hwe_kernel is not None:
                form.set_hwe_kernel(hwe_kernel=hwe_kernel)
            if form.is_valid():
                form.save()
            else:
                raise MAASAPIValidationError(form.errors)

        try:
            node.start(request.user, user_data=user_data, comment=comment)
        except StaticIPAddressExhaustion:
            # The API response should contain error text with the
            # system_id in it, as that is the primary API key to a node.
            raise StaticIPAddressExhaustion(
                "%s: Unable to allocate static IP due to address"
                " exhaustion." % system_id)
        return node

    @operation(idempotent=False)
    def release(self, request, system_id):
        """Release a node.  Opposite of `NodesHandler.acquire`.

        :param comment: Optional comment for the event log.
        :type comment: unicode

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to release the node.
        Returns 409 if the node is in a state where it may not be released.
        """
        comment = get_optional_param(request.POST, 'comment')
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        if node.status == NODE_STATUS.RELEASING or \
                node.status == NODE_STATUS.READY:
            # Nothing to do if this node is already releasing, otherwise
            # this may be a redundant retry, and the
            # postcondition is achieved, so call this success.
            pass
        elif node.status in RELEASABLE_STATUSES:
            node.release_or_erase(request.user, comment)
        else:
            raise NodeStateViolation(
                "Node cannot be released in its current state ('%s')."
                % node.display_status())
        return node

    @operation(idempotent=False)
    def commission(self, request, system_id):
        """Begin commissioning process for a node.

        :param enable_ssh: Whether to enable SSH for the commissioning
            environment using the user's SSH key(s).
        :type enable_ssh: bool ('0' for False, '1' for True)
        :param block_poweroff: Whether to prevent the power off the node
            after the commissioning has completed.
        :type block_poweroff: bool ('0' for False, '1' for True)
        :param skip_networking: Whether to skip re-configuring the networking
            on the node after the commissioning has completed.
        :type skip_networking: bool ('0' for False, '1' for True)

        A node in the 'ready', 'declared' or 'failed test' state may
        initiate a commissioning cycle where it is checked out and tested
        in preparation for transitioning to the 'ready' state. If it is
        already in the 'ready' state this is considered a re-commissioning
        process which is useful if commissioning tests were changed after
        it previously commissioned.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.ADMIN)
        form = CommissionForm(
            instance=node, user=request.user, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=True)
    def details(self, request, system_id):
        """Obtain various system details.

        For example, LLDP and ``lshw`` XML dumps.

        Returns a ``{detail_type: xml, ...}`` map, where
        ``detail_type`` is something like "lldp" or "lshw".

        Note that this is returned as BSON and not JSON. This is for
        efficiency, but mainly because JSON can't do binary content
        without applying additional encoding like base-64.

        Returns 404 if the node is not found.
        """
        node = get_object_or_404(Node, system_id=system_id)
        probe_details = get_single_probed_details(node.system_id)
        probe_details_report = {
            name: None if data is None else bson.Binary(data)
            for name, data in probe_details.items()
        }
        return HttpResponse(
            bson.BSON.encode(probe_details_report),
            # Not sure what media type to use here.
            content_type='application/bson')

    @operation(idempotent=False)
    def claim_sticky_ip_address(self, request, system_id):
        """Assign a "sticky" IP address to a Node's MAC.

        :param mac_address: Optional MAC address on the node on which to
            assign the sticky IP address.  If not passed, defaults to the
            PXE MAC for the node.
        :param requested_address: Optional IP address to claim.  Must be in
            the range defined on a cluster interface to which the context
            MAC is related, or 403 Forbidden is returned.  If the requested
            address is unavailable for use, 404 Not Found is returned.

        A sticky IP is one which stays with the node until the IP is
        disassociated with the node, or the node is deleted.  It allows
        an admin to give a node a stable IP, since normally an automatic
        IP is allocated to a node only during the time a user has
        acquired and started a node.

        Returns 404 if the node is not found.
        Returns 409 if the node is in an allocated state.
        Returns 400 if the mac_address is not found on the node.
        Returns 503 if there are not enough IPs left on the cluster interface
        to which the mac_address is linked.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        if node.status == NODE_STATUS.ALLOCATED:
            raise NodeStateViolation(
                "Sticky IP cannot be assigned to a node that is allocated")

        raw_mac = request.POST.get('mac_address', None)
        if raw_mac is None:
            nic = node.get_boot_interface()
        else:
            try:
                nic = Interface.objects.get(
                    mac_address=raw_mac, node=node)
            except Interface.DoesNotExist:
                raise MAASAPIBadRequest(
                    "mac_address %s not found on the node" % raw_mac)
        requested_address = request.POST.get('requested_address', None)

        form = ClaimIPForm(request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        sticky_ips = nic.claim_static_ips(requested_address=requested_address)
        maaslog.info(
            "%s: Sticky IP address(es) allocated: %s", node.fqdn,
            ', '.join(allocation.ip for allocation in sticky_ips))
        return node

    @operation(idempotent=False)
    def release_sticky_ip_address(self, request, system_id):
        """Release a "sticky" IP address from a node's MAC.

        :param address: Optional IP address to release. If left unspecified,
            will release every "sticky" IP address associated with the node.

        Returns 400 if the specified addresses could not be deallocated
        Returns 404 if the node is not found.
        Returns 409 if the node is in an allocated state.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        address = request.POST.get('address', None)

        form = ReleaseIPForm(request.POST)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        deallocated_ips = []
        if address:
            sip = StaticIPAddress.objects.filter(
                alloc_type=IPADDRESS_TYPE.STICKY, ip=address,
                interface__node=node).first()
            if sip is None:
                raise MAASAPIBadRequest(
                    "%s is not a sticky IP address on node: %s",
                    address, node.hostname)
            for interface in sip.interface_set.all():
                interface.unlink_ip_address(sip)
            deallocated_ips.append(address)
        else:
            for interface in node.interface_set.all():
                for ip_address in interface.ip_addresses.filter(
                        alloc_type=IPADDRESS_TYPE.STICKY, ip__isnull=False):
                    if ip_address.ip:
                        interface.unlink_ip_address(ip_address)
                        deallocated_ips.append(ip_address.ip)

        maaslog.info(
            "%s: Sticky IP address(es) deallocated: %s", node.hostname,
            ', '.join(unicode(ip) for ip in deallocated_ips))
        return node

    @operation(idempotent=False)
    def mark_broken(self, request, system_id):
        """Mark a node as 'broken'.

        If the node is allocated, release it first.

        :param comment: Optional comment for the event log. Will be
            displayed on the Node as an error description until marked fixed.
        :type comment: unicode

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to mark the node
        broken.
        """
        node = Node.nodes.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.EDIT)
        comment = get_optional_param(request.POST, 'comment')
        if not comment:
            # read old error_description to for backward compatibility
            comment = get_optional_param(request.POST, 'error_description')
        node.mark_broken(request.user, comment)
        return node

    @operation(idempotent=False)
    def mark_fixed(self, request, system_id):
        """Mark a broken node as fixed and set its status as 'ready'.

        :param comment: Optional comment for the event log.
        :type comment: unicode

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to mark the node
        fixed.
        """
        comment = get_optional_param(request.POST, 'comment')
        node = Node.nodes.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.ADMIN)
        node.mark_fixed(request.user, comment)
        maaslog.info(
            "%s: User %s marked node as fixed", node.hostname,
            request.user.username)
        return node

    @admin_method
    @operation(idempotent=True)
    def power_parameters(self, request, system_id):
        """Obtain power parameters.

        This method is reserved for admin users and returns a 403 if the
        user is not one.

        This returns the power parameters, if any, configured for a
        node. For some types of power control this will include private
        information such as passwords and secret keys.

        Returns 404 if the node is not found.
        """
        node = get_object_or_404(Node, system_id=system_id)
        return node.power_parameters

    @operation(idempotent=True)
    def query_power_state(self, request, system_id):
        """Query the power state of a node.

        Send a request to the node's power controller which asks it about
        the node's state.  The reply to this could be delayed by up to
        30 seconds while waiting for the power controller to respond.
        Use this method sparingly as it ties up an appserver thread
        while waiting.

        :param system_id: The node to query.
        :return: a dict whose key is "state" with a value of one of
            'on' or 'off'.

        Returns 400 if the node is not installable.
        Returns 404 if the node is not found.
        Returns 503 (with explanatory text) if the power state could not
        be queried.
        """
        node = get_object_or_404(Node, system_id=system_id)
        if not node.installable:
            raise MAASAPIBadRequest(
                "%s: Unable to query power state; not an installable node" %
                node.hostname)

        ng = node.nodegroup

        try:
            client = getClientFor(ng.uuid)
        except NoConnectionsAvailable:
            maaslog.error(
                "Unable to get RPC connection for cluster '%s' (%s)",
                ng.cluster_name, ng.uuid)
            raise PowerProblem("Unable to connect to cluster controller")

        try:
            power_info = node.get_effective_power_info()
        except UnknownPowerType as e:
            raise PowerProblem(e)
        if not power_info.can_be_started:
            raise PowerProblem("Power state is not queryable")

        call = client(
            PowerQuery, system_id=system_id, hostname=node.hostname,
            power_type=power_info.power_type,
            context=power_info.power_parameters)
        try:
            state = call.wait(POWER_QUERY_TIMEOUT)
        except crochet.TimeoutError:
            maaslog.error(
                "%s: Timed out waiting for power response in Node.power_state",
                node.hostname)
            raise PowerProblem("Timed out waiting for power response")
        except (NotImplementedError, PowerActionFail) as e:
            raise PowerProblem(e)

        return state

    @operation(idempotent=False)
    def abort_operation(self, request, system_id):
        """Abort a node's current operation.

        :param comment: Optional comment for the event log.
        :type comment: unicode

        This currently only supports aborting of the 'Disk Erasing' operation.

        Returns 404 if the node could not be found.
        Returns 403 if the user does not have permission to abort the
        current operation.
        """
        comment = get_optional_param(request.POST, 'comment')
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        node.abort_operation(request.user, comment)
        return node

    @operation(idempotent=False)
    def set_storage_layout(self, request, system_id):
        """Changes the storage layout on the node.

        This can only be preformed on an allocated node.

        Note: This will clear the current storage layout and any extra
        configuration and replace it will the new layout.

        :param storage_layout: Storage layout for the node. (flat, lvm
            and bcache)

        The following are optional for all layouts:

        :param boot_size: Size of the boot partition.
        :param root_size: Size of the root partition.
        :param root_device: Physical block device to place the root partition.

        The following are optional for LVM:

        :param vg_name: Name of created volume group.
        :param lv_name: Name of created logical volume.
        :param lv_size: Size of created logical volume.

        The following are optional for Bcache:

        :param cache_device: Physical block device to use as the cache device.
        :param cache_mode: Cache mode for bcache device. (writeback,
            writethrough, writearound)
        :param cache_size: Size of the cache partition to create on the cache
            device.
        :param cache_no_part: Don't create a partition on the cache device.
            Use the entire disk as the cache device.

        Returns 400 if the node is currently not allocated.
        Returns 404 if the node could not be found.
        Returns 403 if the user does not have permission to set the storage
        layout.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        if node.status != NODE_STATUS.ALLOCATED:
            raise MAASAPIBadRequest(
                "Cannot change the storage layout on a node that is "
                "not allocated.")
        storage_layout, _ = get_storage_layout_params(request, required=True)
        try:
            node.set_storage_layout(
                storage_layout, params=request.data, allow_fallback=False)
        except StorageLayoutMissingBootDiskError:
            raise MAASAPIBadRequest(
                "Node is missing a boot disk; no storage layout can be "
                "applied.")
        except StorageLayoutError as e:
            raise MAASAPIBadRequest(
                "Failed to configure storage layout '%s': %s" % (
                    storage_layout, e.message))
        return node

    @operation(idempotent=False)
    def clear_default_gateways(self, request, system_id):
        """Clear any set default gateways on the node.

        This will clear both IPv4 and IPv6 gateways on the node. This will
        transition the logic of identifing the best gateway to MAAS. This logic
        is determined based the following criteria:

        1. Managed subnets over unmanaged subnets.
        2. Bond interfaces over physical interfaces.
        3. Node's boot interface over all other interfaces except bonds.
        4. Physical interfaces over VLAN interfaces.
        5. Sticky IP links over user reserved IP links.
        6. User reserved IP links over auto IP links.

        If the default gateways need to be specific for this node you can set
        which interface and subnet's gateway to use when this node is deployed
        with the `node-interfaces set-default-gateway` API.
        """
        node = Node.nodes.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.ADMIN)
        node.gateway_link_ipv4 = None
        node.gateway_link_ipv6 = None
        node.save()
        return node


def create_node(request):
    """Service an http request to create a node.

    The node will be in the New state.

    :param request: The http request for this node to be created.
    :return: A `Node`.
    :rtype: :class:`maasserver.models.Node`.
    :raises: ValidationError
    """

    # For backwards compatibilty reasons, requests may be sent with:
    #     architecture with a '/' in it: use normally
    #     architecture without a '/' and no subarchitecture: assume 'generic'
    #     architecture without a '/' and a subarchitecture: use as specified
    #     architecture with a '/' and a subarchitecture: error
    given_arch = request.data.get('architecture', None)
    given_subarch = request.data.get('subarchitecture', None)
    given_min_hwe_kernel = request.data.get('min_hwe_kernel', None)
    altered_query_data = request.data.copy()
    if given_arch and '/' in given_arch:
        if given_subarch:
            # Architecture with a '/' and a subarchitecture: error.
            raise MAASAPIValidationError(
                'Subarchitecture cannot be specified twice.')
        # Architecture with a '/' in it: use normally.
    elif given_arch:
        if given_subarch:
            # Architecture without a '/' and a subarchitecture:
            # use as specified.
            altered_query_data['architecture'] = '/'.join(
                [given_arch, given_subarch])
            del altered_query_data['subarchitecture']
        else:
            # Architecture without a '/' and no subarchitecture:
            # assume 'generic'.
            altered_query_data['architecture'] += '/generic'

    hwe_regex = re.compile('hwe-.+')
    has_arch_with_hwe = (
        given_arch and hwe_regex.search(given_arch) is not None)
    has_subarch_with_hwe = (
        given_subarch and hwe_regex.search(given_subarch) is not None)
    if has_arch_with_hwe or has_subarch_with_hwe:
        raise MAASAPIValidationError(
            'hwe kernel must be specified using the min_hwe_kernel argument.')

    if given_min_hwe_kernel:
        if hwe_regex.search(given_min_hwe_kernel) is None:
            raise MAASAPIValidationError(
                'min_hwe_kernel must be in the form of hwe-<LETTER>.')

    if 'nodegroup' not in altered_query_data:
        # If 'nodegroup' is not explicitly specified, get the origin of the
        # request to figure out which nodegroup the new node should be
        # attached to.
        if request.data.get('autodetect_nodegroup', None) is None:
            # We insist on this to protect command-line API users who
            # are manually enlisting nodes.  You can't use the origin's
            # IP address to indicate in which nodegroup the new node belongs.
            raise MAASAPIValidationError(
                "'autodetect_nodegroup' must be specified if 'nodegroup' "
                "parameter missing")
        nodegroup = find_nodegroup(request)
        if nodegroup is not None:
            altered_query_data['nodegroup'] = nodegroup

    Form = get_node_create_form(request.user)
    form = Form(data=altered_query_data, request=request)
    if form.is_valid():
        node = form.save()
        # Hack in the power parameters here.
        store_node_power_parameters(node, request)
        maaslog.info("%s: Enlisted new node", node.hostname)
        return node
    else:
        raise MAASAPIValidationError(form.errors)


class AnonNodesHandler(AnonymousOperationsHandler):
    """Anonymous access to Nodes."""
    create = read = update = delete = None
    model = Node
    fields = DISPLAYED_NODE_FIELDS

    # Override the 'hostname' field so that it returns the FQDN instead as
    # this is used by Juju to reach that node.
    @classmethod
    def hostname(handler, node):
        return node.fqdn

    @operation(idempotent=False)
    def new(self, request):
        # Note: this docstring is duplicated below. Be sure to update both.
        """Create a new Node.

        Adding a server to a MAAS puts it on a path that will wipe its disks
        and re-install its operating system, in the event that it PXE boots.
        In anonymous enlistment (and when the enlistment is done by a
        non-admin), the node is held in the "New" state for approval by a MAAS
        admin.

        The minimum data required is:
        architecture=<arch string> (e.g. "i386/generic")
        mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")
        autodetect_nodegroup=True

        :param architecture: A string containing the architecture type of
            the node. (For example, "i386", or "amd64".) To determine the
            supported architectures, use the boot-resources endpoint.
        :param min_hwe_kernel: A string containing the minimum kernel version
            allowed to be ran on this node.
        :param subarchitecture: A string containing the subarchitecture type
            of the node. (For example, "generic" or "hwe-t".) To determine
            the supported subarchitectures, use the boot-resources endpoint.
        :param mac_addresses: One or more MAC addresses for the node. To
            specify more than one MAC address, the parameter must be specified
            twice. (such as "nodes new mac_addresses=01:02:03:04:05:06
            mac_addresses=02:03:04:05:06:07")
        :param hostname: A hostname. If not given, one will be generated.
        :param power_type: A power management type, if applicable (e.g.
            "virsh", "ipmi").
        :param autodetect_nodegroup: (boolean) Whether or not to attempt
            nodegroup detection for this node. The nodegroup is determined
            based on the requestor's IP address range. (if the API request
            comes from an IP range within a known nodegroup, that nodegroup
            will be used.)
        :param nodegroup: The id of the nodegroup this node belongs to.
        :param boot_type: The installation type of the node. 'fastpath': use
            the default installer. 'di' use the debian installer.
            Note that using 'di' is now deprecated and will be removed in favor
            of the default installer in MAAS 1.9.
        :type boot_type: unicode
        """
        return create_node(request)

    @operation(idempotent=True)
    def is_registered(self, request):
        """Returns whether or not the given MAC address is registered within
        this MAAS (and attached to a non-retired node).

        :param mac_address: The mac address to be checked.
        :type mac_address: unicode
        :return: 'true' or 'false'.
        :rtype: unicode

        Returns 400 if any mandatory parameters are missing.
        """
        mac_address = get_mandatory_param(request.GET, 'mac_address')
        interfaces = Interface.objects.filter(mac_address=mac_address)
        interfaces = interfaces.exclude(node__status=NODE_STATUS.RETIRED)
        return interfaces.exists()

    @operation(idempotent=False)
    def accept(self, request):
        """Accept a node's enlistment: not allowed to anonymous users.

        Always returns 401.
        """
        raise Unauthorized("You must be logged in to accept nodes.")

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodesHandler(OperationsHandler):
    """Manage the collection of all the nodes in the MAAS."""
    api_doc_section_name = "Nodes"
    create = read = update = delete = None
    anonymous = AnonNodesHandler

    @operation(idempotent=False)
    def new(self, request):
        # Note: this docstring is duplicated above. Be sure to update both.
        """Create a new Node.

        Adding a server to a MAAS puts it on a path that will wipe its disks
        and re-install its operating system, in the event that it PXE boots.
        In anonymous enlistment (and when the enlistment is done by a
        non-admin), the node is held in the "New" state for approval by a MAAS
        admin.

        The minimum data required is:
        architecture=<arch string> (e.g. "i386/generic")
        mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")
        autodetect_nodegroup=True

        :param architecture: A string containing the architecture type of
            the node. (For example, "i386", or "amd64".) To determine the
            supported architectures, use the boot-resources endpoint.
        :param min_hwe_kernel: A string containing the minimum kernel version
            allowed to be ran on this node.
        :param subarchitecture: A string containing the subarchitecture type
            of the node. (For example, "generic" or "hwe-t".) To determine
            the supported subarchitectures, use the boot-resources endpoint.
        :param mac_addresses: One or more MAC addresses for the node. To
            specify more than one MAC address, the parameter must be specified
            twice. (such as "nodes new mac_addresses=01:02:03:04:05:06
            mac_addresses=02:03:04:05:06:07")
        :param hostname: A hostname. If not given, one will be generated.
        :param power_type: A power management type, if applicable (e.g.
            "virsh", "ipmi").
        :param autodetect_nodegroup: (boolean) Whether or not to attempt
            nodegroup detection for this node. The nodegroup is determined
            based on the requestor's IP address range. (if the API request
            comes from an IP range within a known nodegroup, that nodegroup
            will be used.)
        :param nodegroup: The id of the nodegroup this node belongs to.
        """
        node = create_node(request)
        if request.user.is_superuser:
            node.accept_enlistment(request.user)
        return node

    def _check_system_ids_exist(self, system_ids):
        """Check that the requested system_ids actually exist in the DB.

        We don't check if the current user has rights to do anything with them
        yet, just that the strings are valid. If not valid raise a BadRequest
        error.
        """
        if not system_ids:
            return
        existing_nodes = Node.nodes.filter(system_id__in=system_ids)
        existing_ids = set(existing_nodes.values_list('system_id', flat=True))
        unknown_ids = system_ids - existing_ids
        if len(unknown_ids) > 0:
            raise MAASAPIBadRequest(
                "Unknown node(s): %s." % ', '.join(unknown_ids))

    @operation(idempotent=False)
    def accept(self, request):
        """Accept declared nodes into the MAAS.

        Nodes can be enlisted in the MAAS anonymously or by non-admin users,
        as opposed to by an admin.  These nodes are held in the New
        state; a MAAS admin must first verify the authenticity of these
        enlistments, and accept them.

        Enlistments can be accepted en masse, by passing multiple nodes to
        this call.  Accepting an already accepted node is not an error, but
        accepting one that is already allocated, broken, etc. is.

        :param nodes: system_ids of the nodes whose enlistment is to be
            accepted.  (An empty list is acceptable).
        :return: The system_ids of any nodes that have their status changed
            by this call.  Thus, nodes that were already accepted are
            excluded from the result.

        Returns 400 if any of the nodes do not exist.
        Returns 403 if the user is not an admin.
        """
        system_ids = set(request.POST.getlist('nodes'))
        # Check the existence of these nodes first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        nodes = Node.nodes.get_nodes(
            request.user, perm=NODE_PERMISSION.ADMIN, ids=system_ids)
        if len(nodes) < len(system_ids):
            permitted_ids = set(node.system_id for node in nodes)
            raise PermissionDenied(
                "You don't have the required permission to accept the "
                "following node(s): %s." % (
                    ', '.join(system_ids - permitted_ids)))
        return filter(
            None, [node.accept_enlistment(request.user) for node in nodes])

    @operation(idempotent=False)
    def accept_all(self, request):
        """Accept all declared nodes into the MAAS.

        Nodes can be enlisted in the MAAS anonymously or by non-admin users,
        as opposed to by an admin.  These nodes are held in the New
        state; a MAAS admin must first verify the authenticity of these
        enlistments, and accept them.

        :return: Representations of any nodes that have their status changed
            by this call.  Thus, nodes that were already accepted are excluded
            from the result.
        """
        nodes = Node.nodes.get_nodes(
            request.user, perm=NODE_PERMISSION.ADMIN)
        nodes = nodes.filter(status=NODE_STATUS.NEW)
        nodes = [node.accept_enlistment(request.user) for node in nodes]
        return filter(None, nodes)

    @operation(idempotent=False)
    def check_commissioning(self, request):
        """Check all commissioning nodes to see if they are taking too long.

        Anything that has been commissioning for longer than
        settings.COMMISSIONING_TIMEOUT is moved into the
        FAILED_COMMISSIONING status.
        """
        # Compute the cutoff time on the database, using the database's
        # clock to compare to the "updated" timestamp, also set from the
        # database's clock.  Otherwise, a sufficient difference between the
        # two clocks (including timezone offset!) might cause commissioning to
        # "time out" immediately, or hours late.
        #
        # This timeout relies on nothing else updating the commissioning node
        # within the hour.  Otherwise, the timestamp will be refreshed as a
        # side effect and timeout will be postponed.
        #
        # This query both identifies and updates the failed nodes.  It
        # refreshes the "updated" timestamp, but does not run any Django-side
        # code associated with saving the nodes.
        params = {
            'commissioning': NODE_STATUS.COMMISSIONING,
            'failed_tests': NODE_STATUS.FAILED_COMMISSIONING,
            'minutes': settings.COMMISSIONING_TIMEOUT
        }
        query = Node.nodes.raw("""
            UPDATE maasserver_node
            SET
                status = %(failed_tests)s,
                updated = now()
            WHERE
                status = %(commissioning)s AND
                updated <= (now() - interval '%(minutes)f minutes')
            RETURNING *
            """ % params)
        results = list(query)
        # Note that Django doesn't call save() on updated nodes here,
        # but I don't think anything requires its effects anyway.
        return results

    @operation(idempotent=False)
    def release(self, request):
        """Release multiple nodes.

        This places the nodes back into the pool, ready to be reallocated.

        :param nodes: system_ids of the nodes which are to be released.
           (An empty list is acceptable).
        :param comment: Optional comment for the event log.
        :type comment: unicode
        :return: The system_ids of any nodes that have their status
            changed by this call. Thus, nodes that were already released
            are excluded from the result.

        Returns 400 if any of the nodes cannot be found.
        Returns 403 if the user does not have permission to release any of
        the nodes.
        Returns a 409 if any of the nodes could not be released due to their
        current state.
        """
        system_ids = set(request.POST.getlist('nodes'))
        comment = get_optional_param(request.POST, 'comment')
        # Check the existence of these nodes first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        nodes = Node.nodes.get_nodes(
            request.user, perm=NODE_PERMISSION.EDIT, ids=system_ids)
        if len(nodes) < len(system_ids):
            permitted_ids = set(node.system_id for node in nodes)
            raise PermissionDenied(
                "You don't have the required permission to release the "
                "following node(s): %s." % (
                    ', '.join(system_ids - permitted_ids)))

        released_ids = []
        failed = []
        for node in nodes:
            if node.status == NODE_STATUS.READY:
                # Nothing to do.
                pass
            elif node.status in RELEASABLE_STATUSES:
                node.release_or_erase(request.user, comment)
                released_ids.append(node.system_id)
            else:
                failed.append(
                    "%s ('%s')"
                    % (node.system_id, node.display_status()))

        if any(failed):
            raise NodeStateViolation(
                "Node(s) cannot be released in their current state: %s."
                % ', '.join(failed))
        return released_ids

    @operation(idempotent=True)
    def list(self, request):
        """List all nodes."""
        nodes = filtered_nodes_list_from_request(request)

        # Prefetch related objects that are needed for rendering the result.
        nodes = nodes.prefetch_related('interface_set__node')
        nodes = nodes.prefetch_related(
            'interface_set__ip_addresses')
        nodes = nodes.prefetch_related('tags')
        nodes = nodes.select_related('nodegroup')
        nodes = nodes.prefetch_related('nodegroup__nodegroupinterface_set')
        nodes = nodes.prefetch_related('zone')
        return nodes.order_by('id')

    @operation(idempotent=True)
    def list_allocated(self, request):
        """Fetch Nodes that were allocated to the User/oauth token."""
        token = get_oauth_token(request)
        match_ids = get_optional_list(request.GET, 'id')
        nodes = Node.nodes.get_allocated_visible_nodes(token, match_ids)
        return nodes.order_by('id')

    @operation(idempotent=False)
    def acquire(self, request):
        """Acquire an available node for deployment.

        Constraints parameters can be used to acquire a node that possesses
        certain characteristics.  All the constraints are optional and when
        multiple constraints are provided, they are combined using 'AND'
        semantics.

        :param name: Hostname of the returned node.
        :type name: unicode
        :param arch: Architecture of the returned node (e.g. 'i386/generic',
            'amd64', 'armhf/highbank', etc.).
        :type arch: unicode
        :param cpu_count: The minium number of CPUs the returned node must
            have.
        :type cpu_count: int
        :param mem: The minimum amount of memory (expressed in MB) the
             returned node must have.
        :type mem: float
        :param tags: List of tags the returned node must have.
        :type tags: list of unicodes
        :param not_tags: List of tags the acquired node must not have.
        :type tags: List of unicodes.
        :param connected_to: List of routers' MAC addresses the returned
            node must be connected to.
        :type connected_to: unicode or list of unicodes
        :param networks: List of networks (defined in MAAS) to which the node
            must be attached.  A network can be identified by the name
            assigned to it in MAAS; or by an `ip:` prefix followed by any IP
            address that falls within the network; or a `vlan:` prefix
            followed by a numeric VLAN tag, e.g. `vlan:23` for VLAN number 23.
            Valid VLAN tags must be in the range of 1 to 4095 inclusive.
        :type networks: list of unicodes
        :param not_networks: List of networks (defined in MAAS) to which the
            node must not be attached.  The returned noded won't be attached to
            any of the specified networks.  A network can be identified by the
            name assigned to it in MAAS; or by an `ip:` prefix followed by any
            IP address that falls within the network; or a `vlan:` prefix
            followed by a numeric VLAN tag, e.g. `vlan:23` for VLAN number 23.
            Valid VLAN tags must be in the range of 1 to 4095 inclusive.
        :type not_networks: list of unicodes
        :param not_connected_to: List of routers' MAC Addresses the returned
            node must not be connected to.
        :type connected_to: list of unicodes
        :param zone: An optional name for a physical zone the acquired
            node should be located in.
        :type zone: unicode
        :type not_in_zone: Optional list of physical zones from which the
            node should not be acquired.
        :type not_in_zone: List of unicodes.
        :param agent_name: An optional agent name to attach to the
            acquired node.
        :type agent_name: unicode
        :param comment: Optional comment for the event log.
        :type comment: unicode

        Returns 409 if a suitable node matching the constraints could not be
        found.
        """
        form = AcquireNodeForm(data=request.data)
        comment = get_optional_param(request.POST, 'comment')
        maaslog.info(
            "Request from user %s to acquire a node with constraints %s",
            request.user.username, request.data)

        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)

        # This lock prevents a node we've picked as available from
        # becoming unavailable before our transaction commits.
        with locks.node_acquire:
            nodes = Node.nodes.get_available_nodes_for_acquisition(
                request.user)
            nodes, constraint_map = form.filter_nodes(nodes)
            node = get_first(nodes)
            if node is None:
                constraints = form.describe_constraints()
                if constraints == '':
                    # No constraints. That means no nodes at all were
                    # available.
                    message = "No node available."
                else:
                    message = (
                        "No available node matches constraints: %s"
                        % constraints)
                raise NodesNotAvailable(message)
            agent_name = request.data.get('agent_name', '')
            node.acquire(
                request.user, get_oauth_token(request),
                agent_name=agent_name, comment=comment)
            node.constraint_map = constraint_map.get(node.id, {})
            return node

    @admin_method
    @operation(idempotent=False)
    def set_zone(self, request):
        """Assign multiple nodes to a physical zone at once.

        :param zone: Zone name.  If omitted, the zone is "none" and the nodes
            will be taken out of their physical zones.
        :param nodes: system_ids of the nodes whose zones are to be set.
           (An empty list is acceptable).

        Raises 403 if the user is not an admin.
        """
        data = {
            'action': 'set_zone',
            'zone': request.data.get('zone'),
            'system_id': get_optional_list(request.data, 'nodes'),
        }
        form = BulkNodeActionForm(request.user, data=data)
        if not form.is_valid():
            raise MAASAPIValidationError(form.errors)
        form.save()

    @admin_method
    @operation(idempotent=True)
    def power_parameters(self, request):
        """Retrieve power parameters for multiple nodes.

        :param id: An optional list of system ids.  Only nodes with
            matching system ids will be returned.
        :type id: iterable

        :return: A dictionary of power parameters, keyed by node system_id.

        Raises 403 if the user is not an admin.
        """
        match_ids = get_optional_list(request.GET, 'id')

        if match_ids is None:
            nodes = Node.nodes.all()
        else:
            nodes = Node.nodes.filter(system_id__in=match_ids)

        return {node.system_id: node.power_parameters for node in nodes}

    @operation(idempotent=True)
    def deployment_status(self, request):
        """Retrieve deployment status for multiple nodes.

        :param nodes: Mandatory list of system IDs for nodes whose status
            you wish to check.

        Returns 400 if mandatory parameters are missing.
        Returns 403 if the user has no permission to view any of the nodes.
        """
        system_ids = set(request.GET.getlist('nodes'))
        # Check the existence of these nodes first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        nodes = Node.nodes.get_nodes(
            request.user, perm=NODE_PERMISSION.VIEW, ids=system_ids)
        permitted_ids = set(node.system_id for node in nodes)
        if len(nodes) != len(system_ids):
            raise PermissionDenied(
                "You don't have the required permission to view the "
                "following node(s): %s." % (
                    ', '.join(system_ids - permitted_ids)))

        # Create a dict of system_id to status.
        response = dict()
        for node in nodes:
            response[node.system_id] = node.get_deployment_status()
        return response

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])
