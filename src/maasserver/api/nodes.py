# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "AnonNodesHandler",
    "NodeHandler",
    "NodesHandler",
    "store_node_power_parameters",
]

from base64 import b64decode
from itertools import chain
import json

import bson
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.support import (
    admin_method,
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    get_mandatory_param,
    get_optional_list,
    get_optional_param,
)
from maasserver.clusterrpc.driver_parameters import get_driver_types
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_TYPE,
    NODE_TYPE_CHOICES,
)
from maasserver.exceptions import (
    ClusterUnavailable,
    MAASAPIBadRequest,
    MAASAPIValidationError,
    NodeStateViolation,
    NoScriptsFound,
    StaticIPAddressExhaustion,
)
from maasserver.fields import MAC_RE
from maasserver.forms import BulkNodeActionForm
from maasserver.forms.ephemeral import TestForm
from maasserver.models import (
    Filesystem,
    Interface,
    ISCSIBlockDevice,
    Node,
    OwnerData,
    PhysicalBlockDevice,
    VirtualBlockDevice,
)
from maasserver.models.nodeprobeddetails import get_single_probed_details
from maasserver.utils.orm import prefetch_queryset
from metadataserver.enum import (
    HARDWARE_TYPE,
    RESULT_TYPE,
    SCRIPT_STATUS,
    SCRIPT_STATUS_CHOICES,
)
from metadataserver.models.scriptset import get_status_from_qs
from piston3.utils import rc
from provisioningserver.drivers.power import UNKNOWN_POWER_TYPE


NODES_SELECT_RELATED = (
    'bmc',
    'controllerinfo',
    'owner',
    'zone',
)

NODES_PREFETCH = [
    'domain__dnsresource_set__ip_addresses',
    'domain__dnsresource_set__dnsdata_set',
    'ownerdata_set',
    'special_filesystems',
    'gateway_link_ipv4__subnet',
    'gateway_link_ipv6__subnet',
    Prefetch(
        'blockdevice_set__filesystem_set',
        queryset=Filesystem.objects.select_related(
            'cache_set', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__partitiontable_set__partitions__filesystem_set',
        queryset=Filesystem.objects.select_related(
            'cache_set', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__iscsiblockdevice',
        queryset=ISCSIBlockDevice.objects.select_related('node'),
    ),
    Prefetch(
        'blockdevice_set__iscsiblockdevice__filesystem_set',
        queryset=Filesystem.objects.select_related(
            'cache_set', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__iscsiblockdevice__partitiontable_set__partitions__'
        'filesystem_set',
        queryset=Filesystem.objects.select_related(
            'cache_set', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__physicalblockdevice',
        queryset=PhysicalBlockDevice.objects.select_related('node'),
    ),
    Prefetch(
        'blockdevice_set__physicalblockdevice__filesystem_set',
        queryset=Filesystem.objects.select_related(
            'cache_set', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__physicalblockdevice__partitiontable_set__'
        'partitions__filesystem_set',
        queryset=Filesystem.objects.select_related(
            'cache_set', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__virtualblockdevice',
        queryset=VirtualBlockDevice.objects.select_related(
            'node', 'filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__virtualblockdevice__filesystem_set',
        queryset=Filesystem.objects.select_related('filesystem_group'),
    ),
    Prefetch(
        'blockdevice_set__virtualblockdevice__partitiontable_set__'
        'partitions__filesystem_set',
        queryset=Filesystem.objects.select_related('filesystem_group'),
    ),
    'boot_interface__node',
    'boot_interface__vlan__primary_rack',
    'boot_interface__vlan__secondary_rack',
    'boot_interface__vlan__fabric__vlan_set',
    'boot_interface__vlan__space',
    'boot_interface__ip_addresses__subnet',
    'boot_interface__parents',
    ('boot_interface__children_relationships__child__'
     'children_relationships__child'),
    'interface_set__vlan__primary_rack',
    'interface_set__vlan__secondary_rack',
    'interface_set__vlan__fabric__vlan_set',
    'interface_set__vlan__space',
    'interface_set__parents',
    'interface_set__ip_addresses__subnet',
    # Prefetch 3 levels deep, anything more will require extra queries.
    'interface_set__children_relationships__child__vlan',
    ('interface_set__children_relationships__child__'
     'children_relationships__child__vlan'),
    ('interface_set__children_relationships__child__'
     'children_relationships__child__'
     'children_relationships__child__vlan'),
    'tags',
    'nodemetadata_set',
]


def store_node_power_parameters(node, request):
    """Store power parameters in request.

    The parameters should be JSON, passed with key `power_parameters`.
    """
    power_type = request.POST.get("power_type", None)
    if power_type is None:
        return

    power_types = get_driver_types(ignore_errors=True)
    if len(power_types) == 0:
        raise ClusterUnavailable(
            "No rack controllers connected to validate the power_type.")

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


def filtered_nodes_list_from_request(request, model=None):
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
    :param domain: An optional name for a dns domain. Only events relating to
        the nodes in the domain will be returned.
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

    if model is None:
        model = Node
    # Fetch nodes and apply filters.
    nodes = model.objects.get_nodes(
        request.user, NODE_PERMISSION.VIEW, ids=match_ids)
    if match_macs is not None:
        nodes = nodes.filter(interface__mac_address__in=match_macs)
    match_hostnames = get_optional_list(request.GET, 'hostname')
    if match_hostnames is not None:
        nodes = nodes.filter(hostname__in=match_hostnames)
    match_domains = get_optional_list(request.GET, 'domain')
    if match_domains is not None:
        nodes = nodes.filter(domain__name__in=match_domains)
    match_zone_name = request.GET.get('zone', None)
    if match_zone_name is not None:
        nodes = nodes.filter(zone__name=match_zone_name)
    match_agent_name = request.GET.get('agent_name', None)
    if match_agent_name is not None:
        nodes = nodes.filter(agent_name=match_agent_name)

    return nodes.order_by('id')


def is_registered(request):
    """Used by both `NodesHandler` and `AnonNodesHandler`."""
    mac_address = get_mandatory_param(request.GET, 'mac_address')
    interfaces = Interface.objects.filter(mac_address=mac_address)
    interfaces = interfaces.exclude(node__isnull=True)
    interfaces = interfaces.exclude(node__status=NODE_STATUS.RETIRED)
    return interfaces.exists()


def get_cached_script_results(node):
    """Load script results into cache and return the cached list."""
    if not hasattr(node, '_cached_script_results'):
        node._cached_script_results = list(node.get_latest_script_results)
        node._cached_commissioning_script_results = []
        node._cached_testing_script_results = []
        for script_result in node._cached_script_results:
            if (script_result.script_set.result_type ==
                    RESULT_TYPE.INSTALLATION):
                # Don't include installation results in the health
                # status.
                continue
            elif script_result.status == SCRIPT_STATUS.ABORTED:
                # LP: #1724235 - Ignore aborted scripts.
                continue
            elif (script_result.script_set.result_type ==
                    RESULT_TYPE.COMMISSIONING):
                node._cached_commissioning_script_results.append(script_result)
            elif (script_result.script_set.result_type ==
                    RESULT_TYPE.TESTING):
                node._cached_testing_script_results.append(script_result)

    return node._cached_script_results


def get_script_status_name(script_status):
    for id, name in SCRIPT_STATUS_CHOICES:
        if id == script_status:
            return name
    return 'Unknown'


class NodeHandler(OperationsHandler):
    """Manage an individual Node.

    The Node is identified by its system_id.
    """
    api_doc_section_name = "Node"

    # Disable create and update
    create = update = None
    model = Node

    # Override 'owner' so it emits the owner's name rather than a
    # full nested user object.
    @classmethod
    def owner(handler, node):
        if node.owner is None:
            return None
        return node.owner.username

    @classmethod
    def node_type_name(handler, node):
        return NODE_TYPE_CHOICES[node.node_type][1]

    @classmethod
    def current_commissioning_result_id(handler, node):
        return node.current_commissioning_script_set_id

    @classmethod
    def current_testing_result_id(handler, node):
        return node.current_testing_script_set_id

    @classmethod
    def current_installation_result_id(handler, node):
        return node.current_installation_script_set_id

    @classmethod
    def commissioning_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(node._cached_commissioning_script_results)

    @classmethod
    def commissioning_status_name(handler, node):
        return get_script_status_name(handler.commissioning_status(node))

    @classmethod
    def testing_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs(node._cached_testing_script_results)

    @classmethod
    def testing_status_name(handler, node):
        return get_script_status_name(handler.testing_status(node))

    @classmethod
    def cpu_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs([
            script_result for script_result
            in node._cached_testing_script_results
            if script_result.script.hardware_type == HARDWARE_TYPE.CPU])

    @classmethod
    def cpu_test_status_name(handler, node):
        return get_script_status_name(handler.cpu_test_status(node))

    @classmethod
    def memory_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs([
            script_result for script_result
            in node._cached_testing_script_results
            if script_result.script.hardware_type == HARDWARE_TYPE.MEMORY])

    @classmethod
    def memory_test_status_name(handler, node):
        return get_script_status_name(handler.memory_test_status(node))

    @classmethod
    def storage_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs([
            script_result for script_result
            in node._cached_testing_script_results
            if script_result.script.hardware_type == HARDWARE_TYPE.STORAGE])

    @classmethod
    def storage_test_status_name(handler, node):
        return get_script_status_name(handler.storage_test_status(node))

    @classmethod
    def other_test_status(handler, node):
        get_cached_script_results(node)
        return get_status_from_qs([
            script_result for script_result
            in node._cached_testing_script_results
            if script_result.script.hardware_type == HARDWARE_TYPE.NODE])

    @classmethod
    def other_test_status_name(handler, node):
        return get_script_status_name(handler.other_test_status(node))

    @classmethod
    def hardware_info(handler, node):
        ret = {
            'system_vendor': 'Unknown',
            'system_product': 'Unknown',
            'system_version': 'Unknown',
            'system_serial': 'Unknown',
            'cpu_model': 'Unknown',
            'mainboard_vendor': 'Unknown',
            'mainboard_product': 'Unknown',
            'mainboard_firmware_version': 'Unknown',
            'mainboard_firmware_date': 'Unknown',
        }
        # Iterate over the NodeMetadata objects instead of filtering to
        # avoid another database call as the values have been prefetched.
        for nmd in node.nodemetadata_set.all():
            # The NodeMetdata model may contain values that shouldn't be
            # shown here. Only set the ones we expect.
            if nmd.key in ret:
                ret[nmd.key] = nmd.value
        return ret

    def read(self, request, system_id):
        """Read a specific Node.

        Returns 404 if the node is not found.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)
        if self.model != Node:
            return node
        else:
            # Return the specific node type object so we get the correct
            # listing
            return node.as_self()

    def delete(self, request, system_id):
        """Delete a specific Node.

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to delete the node.
        Returns 204 if the node is successfully deleted.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        node.as_self().delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, node=None):
        #
        # This method is called by Piston in two different contexts:
        #
        # 1. When generating a URI template to be used in the documentation,
        #    in which case it is called with `node=None`. We return argument
        #    *names* instead of their values. Frustratingly, Piston itself
        #    discards these names and instead uses names derived from Django's
        #    URL patterns for the resource.
        #
        # 2. When populating the `resource_uri` field of an object returned by
        #    the API, in which case `node` is an instance of `Node`.
        #
        # There is a check made at handler class creation time to ensure that
        # the names from #1 match up to the handler's `fields`. In this way we
        # can declare which fields are required to render a resource's URI and
        # be sure that they are all present in a rendering of said resource.
        #
        # There is an additional unit test (see `TestResourceURIs`) to check
        # that the fields in each URI template match up to those fields
        # declared in a handler's `resource_uri` method.
        #
        node_system_id = "system_id"
        if node is not None:
            node_system_id = node.system_id
        return ('node_handler', (node_system_id, ))

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
        node = get_object_or_404(self.model, system_id=system_id)
        probe_details = get_single_probed_details(node)
        probe_details_report = {
            name: None if data is None else bson.Binary(data)
            for name, data in probe_details.items()
        }
        return HttpResponse(
            bson.BSON.encode(probe_details_report),
            # Not sure what media type to use here.
            content_type='application/bson')

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
        node = get_object_or_404(self.model, system_id=system_id)
        return node.power_parameters


class AnonNodeHandler(AnonymousOperationsHandler):
    """Anonymous access to Node."""
    read = create = update = delete = None
    model = Node

    resource_uri = NodeHandler.resource_uri


class AnonNodesHandler(AnonymousOperationsHandler):
    """Anonymous access to Nodes."""
    create = read = update = delete = None

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
        return is_registered(request)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodesHandler(OperationsHandler):
    """Manage the collection of all the nodes in the MAAS."""
    api_doc_section_name = "Nodes"
    create = update = delete = None
    anonymous = AnonNodesHandler
    base_model = Node

    def read(self, request):
        """List Nodes visible to the user, optionally filtered by criteria.

        Nodes are sorted by id (i.e. most recent last) and grouped by type.

        :param hostname: An optional hostname. Only nodes relating to the node
            with the matching hostname will be returned. This can be specified
            multiple times to see multiple nodes.
        :type hostname: unicode

        :param mac_address: An optional MAC address. Only nodes relating to the
            node owning the specified MAC address will be returned. This can be
            specified multiple times to see multiple nodes.
        :type mac_address: unicode

        :param id: An optional list of system ids.  Only nodes relating to the
            nodes with matching system ids will be returned.
        :type id: unicode

        :param domain: An optional name for a dns domain. Only nodes relating
            to the nodes in the domain will be returned.
        :type domain: unicode

        :param zone: An optional name for a physical zone. Only nodes relating
            to the nodes in the zone will be returned.
        :type zone: unicode

        :param agent_name: An optional agent name.  Only nodes relating to the
            nodes with matching agent names will be returned.
        :type agent_name: unicode
        """

        if self.base_model == Node:
            # Avoid circular dependencies
            from maasserver.api.devices import DevicesHandler
            from maasserver.api.machines import MachinesHandler
            from maasserver.api.rackcontrollers import RackControllersHandler
            from maasserver.api.regioncontrollers import (
                RegionControllersHandler
            )
            racks = RackControllersHandler().read(request).order_by("id")
            nodes = list(chain(
                DevicesHandler().read(request).order_by("id"),
                MachinesHandler().read(request).order_by("id"),
                racks,
                RegionControllersHandler().read(request).exclude(
                    id__in=racks).order_by("id"),
            ))
            return nodes
        else:
            nodes = filtered_nodes_list_from_request(request, self.base_model)
            nodes = nodes.select_related(*NODES_SELECT_RELATED)
            nodes = prefetch_queryset(
                nodes, NODES_PREFETCH).order_by('id')
            # Set related node parents so no extra queries are needed.
            for node in nodes:
                for interface in node.interface_set.all():
                    interface.node = node
                for block_device in node.blockdevice_set.all():
                    block_device.node = node
            return nodes

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
        return is_registered(request)

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

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class OwnerDataMixin:
    """Mixin that adds the owner_data classmethod and proves set_owner_data
    to the handler."""

    @classmethod
    def owner_data(handler, machine):
        """Owner data placed on machine."""
        return {
            data.key: data.value
            for data in machine.ownerdata_set.all()
        }

    @operation(idempotent=False)
    def set_owner_data(self, request, system_id):
        """Set key/value data for the current owner.

        Pass any key/value data to this method to add, modify, or remove. A key
        is removed when the value for that key is set to an empty string.

        This operation will not remove any previous keys unless explicitly
        passed with an empty string. All owner data is removed when the machine
        is no longer allocated to a user.

        Returns 404 if the machine is not found.
        Returns 403 if the user does not have permission.
        """
        node = self.model.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.EDIT)
        owner_data = {
            key: None if value == "" else value
            for key, value in request.POST.items()
            if key != "op"
        }
        OwnerData.objects.set_owner_data(node, owner_data)
        return node


class PowerMixin:
    """Mixin which adds power commands to a node type."""

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

        Returns 404 if the node is not found.
        Returns node's power state.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.VIEW)
        return {
            "state": node.power_query().wait(45),
        }

    @operation(idempotent=False)
    def power_on(self, request, system_id):
        """Turn on a node.

        :param user_data: If present, this blob of user-data to be made
            available to the nodes through the metadata service.
        :type user_data: base64-encoded unicode
        :param comment: Optional comment for the event log.
        :type comment: unicode

        Ideally we'd have MIME multipart and content-transfer-encoding etc.
        deal with the encapsulation of binary data, but couldn't make it work
        with the framework in reasonable time so went for a dumb, manual
        encoding instead.

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to start the machine.
        Returns 503 if the start-up attempted to allocate an IP address,
        and there were no IP addresses available on the relevant cluster
        interface.
        """
        user_data = request.POST.get('user_data', None)
        comment = get_optional_param(request.POST, 'comment')

        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        if node.owner is None and node.node_type != NODE_TYPE.RACK_CONTROLLER:
            raise NodeStateViolation(
                "Can't start node: it hasn't been allocated.")
        if user_data is not None:
            user_data = b64decode(user_data)
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
    def power_off(self, request, system_id):
        """Power off a node.

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
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        power_action_sent = node.stop(
            request.user, stop_mode=stop_mode, comment=comment)
        if power_action_sent:
            return node
        else:
            return None

    @operation(idempotent=False)
    def test(self, request, system_id):
        """Begin testing process for a node.

        :param enable_ssh: Whether to enable SSH for the testing environment
            using the user's SSH key(s).
        :type enable_ssh: bool ('0' for False, '1' for True)
        :param testing_scripts: A comma seperated list of testing script names
            and tags to be run. By default all tests tagged 'commissioning'
            will be run.
        :type testing_scripts: string

        A node in the 'ready', 'allocated', 'deployed', 'broken', or any failed
        state may run tests. If testing is started and successfully passes from
        a 'broken', or any failed state besides 'failed commissioning' the node
        will be returned to a ready state. Otherwise the node will return to
        the state it was when testing started.

        Returns 404 if the node is not found.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.ADMIN)
        form = TestForm(instance=node, user=request.user, data=request.data)
        if form.is_valid():
            try:
                return form.save()
            except NoScriptsFound:
                raise MAASAPIValidationError('No testing scripts found!')
        else:
            raise MAASAPIValidationError(form.errors)

    @operation(idempotent=False)
    def override_failed_testing(self, request, system_id):
        """Ignore failed tests and put node back into a usable state.

        :param comment: Optional comment for the event log.
        :type comment: unicode

        Returns 404 if the machine is not found.
        Returns 403 if the user does not have permission to ignore tests for
        the node.
        """
        comment = get_optional_param(request.POST, 'comment')
        node = self.model.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.ADMIN)
        node.override_failed_testing(request.user, comment)
        return node

    @operation(idempotent=False)
    def abort(self, request, system_id):
        """Abort a node's current operation.

        :param comment: Optional comment for the event log.
        :type comment: unicode

        Returns 404 if the node could not be found.
        Returns 403 if the user does not have permission to abort the
        current operation.
        """
        comment = get_optional_param(request.POST, 'comment')
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.EDIT)
        node.abort_operation(request.user, comment)
        return node


class PowersMixin:
    """Mixin which adds power commands to a nodes type."""

    @admin_method
    @operation(idempotent=True)
    def power_parameters(self, request):
        """Retrieve power parameters for multiple machines.

        :param id: An optional list of system ids.  Only machines with
            matching system ids will be returned.
        :type id: iterable

        :return: A dictionary of power parameters, keyed by machine system_id.

        Raises 403 if the user is not an admin.
        """
        match_ids = get_optional_list(request.GET, 'id')

        if match_ids is None:
            machines = self.base_model.objects.all()
        else:
            machines = self.base_model.objects.filter(system_id__in=match_ids)

        return {machine.system_id: machine.power_parameters
                for machine in machines}
