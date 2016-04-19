# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "AnonNodesHandler",
    "NodeHandler",
    "NodesHandler",
    "store_node_power_parameters",
]

from itertools import chain
import json

import bson
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
)
from maasserver.clusterrpc.power_parameters import get_power_types
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    NODE_TYPE_CHOICES,
)
from maasserver.exceptions import (
    ClusterUnavailable,
    MAASAPIBadRequest,
    MAASAPIValidationError,
)
from maasserver.fields import MAC_RE
from maasserver.forms import BulkNodeActionForm
from maasserver.models import (
    Interface,
    Node,
    OwnerData,
)
from maasserver.models.node import typecast_to_node_type
from maasserver.models.nodeprobeddetails import get_single_probed_details
from piston3.utils import rc
from provisioningserver.power.schema import UNKNOWN_POWER_TYPE


def store_node_power_parameters(node, request):
    """Store power parameters in request.

    The parameters should be JSON, passed with key `power_parameters`.
    """
    power_type = request.POST.get("power_type", None)
    if power_type is None:
        return

    power_types = get_power_types(ignore_errors=True)
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
            return typecast_to_node_type(node)

    def delete(self, request, system_id):
        """Delete a specific Node.

        Returns 404 if the node is not found.
        Returns 403 if the user does not have permission to delete the node.
        Returns 204 if the node is successfully deleted.
        """
        node = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        typecast_to_node_type(node).delete()
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
        probe_details = get_single_probed_details(node.system_id)
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
        node = get_object_or_404(self.model, system_id=system_id)
        return {
            "state": node.power_query().wait(45),
        }


class AnonNodeHandler(AnonymousOperationsHandler):
    """Anonymous access to Node."""
    read = create = update = delete = None
    model = Node


class AnonNodesHandler(AnonymousOperationsHandler):
    """Anonymous access to Nodes."""
    create = update = delete = None

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
            nodes = list(chain(
                DevicesHandler().read(request).order_by("id"),
                MachinesHandler().read(request).order_by("id"),
                RackControllersHandler().read(request).order_by("id"),
            ))
            return nodes
        else:
            nodes = filtered_nodes_list_from_request(request, self.base_model)
            # Prefetch related objects that are needed for rendering the
            # result.
            nodes = nodes.prefetch_related('interface_set__node')
            nodes = nodes.prefetch_related('interface_set__ip_addresses')
            nodes = nodes.prefetch_related('tags')
            nodes = nodes.prefetch_related('zone')
            return nodes.order_by('id')

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
            for data in OwnerData.objects.filter(node=machine)
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
