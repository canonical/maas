# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Restful MAAS API.

This is the documentation for the API that lets you control and query MAAS.
The API is "Restful", which means that you access it through normal HTTP
requests.


API versions
------------

At any given time, MAAS may support multiple versions of its API.  The version
number is included in the API's URL, e.g. /api/1.0/

For now, 1.0 is the only supported version.


HTTP methods and parameter-passing
----------------------------------

The following HTTP methods are available for accessing the API:
 * GET (for information retrieval and queries),
 * POST (for asking the system to do things),
 * PUT (for updating objects), and
 * DELETE (for deleting objects).

All methods except DELETE may take parameters, but they are not all passed in
the same way.  GET parameters are passed in the URL, as is normal with a GET:
"/item/?foo=bar" passes parameter "foo" with value "bar".

POST and PUT are different.  Your request should have MIME type
"multipart/form-data"; each part represents one parameter (for POST) or
attribute (for PUT).  Each part is named after the parameter or attribute it
contains, and its contents are the conveyed value.

All parameters are in text form.  If you need to submit binary data to the
API, don't send it as any MIME binary format; instead, send it as a plain text
part containing base64-encoded data.

Most resources offer a choice of GET or POST operations.  In those cases these
methods will take one special parameter, called `op`, to indicate what it is
you want to do.

For example, to list all nodes, you might GET "/api/1.0/nodes/?op=list".
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "AccountHandler",
    "AnonNodeGroupsHandler",
    "AnonNodesHandler",
    "api_doc",
    "api_doc_title",
    "BootImageHandler",
    "BootImagesHandler",
    "BootSourceHandler",
    "BootSourcesHandler",
    "BootSourceSelectionHandler",
    "BootSourceSelectionsHandler",
    "CommissioningScriptHandler",
    "CommissioningScriptsHandler",
    "CommissioningResultsHandler",
    "FileHandler",
    "FilesHandler",
    "get_oauth_token",
    "MaasHandler",
    "NetworkHandler",
    "NetworksHandler",
    "NodeGroupHandler",
    "NodeGroupsHandler",
    "NodeGroupInterfaceHandler",
    "NodeGroupInterfacesHandler",
    "NodeHandler",
    "NodeMacHandler",
    "NodeMacsHandler",
    "NodesHandler",
    "SSHKeyHandler",
    "TagHandler",
    "TagsHandler",
    "pxeconfig",
    "render_api_docs",
    "store_node_power_parameters",
    "UserHandler",
    "UsersHandler",
    "ZoneHandler",
    "ZonesHandler",
    ]

from base64 import (
    b64decode,
    b64encode,
    )
from cStringIO import StringIO
from datetime import (
    datetime,
    timedelta,
    )
from functools import partial
import httplib
from inspect import getdoc
import sys
from textwrap import dedent
from urlparse import urlparse
from xml.sax.saxutils import quoteattr

import bson
from celery.app import app_or_default
from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.core.urlresolvers import reverse
from django.db.utils import DatabaseError
from django.http import (
    Http404,
    HttpResponse,
    )
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from docutils import core
from formencode import validators
from maasserver.api_support import (
    admin_method,
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
    )
from maasserver.api_utils import (
    extract_bool,
    extract_oauth_key,
    get_list_from_dict_or_multidict,
    get_mandatory_param,
    get_oauth_token,
    get_optional_list,
    get_optional_param,
    )
from maasserver.apidoc import (
    describe_resource,
    find_api_resources,
    generate_api_docs,
    generate_power_types_doc,
    )
from maasserver.clusterrpc.power_parameters import (
    get_all_power_types_from_clusters,
    get_power_types,
    )
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
    )
from maasserver.enum import (
    COMPONENT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODEGROUP_STATUS,
    PRESEED_TYPE,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodesNotAvailable,
    NodeStateViolation,
    StaticIPAddressExhaustion,
    Unauthorized,
    )
from maasserver.fields import (
    MAC_RE,
    validate_mac,
    )
from maasserver.forms import (
    BootSourceForm,
    BootSourceSelectionForm,
    BulkNodeActionForm,
    DownloadProgressForm,
    get_action_form,
    get_node_create_form,
    get_node_edit_form,
    NetworkConnectMACsForm,
    NetworkDisconnectMACsForm,
    NetworkForm,
    NetworksListingForm,
    NodeActionForm,
    NodeGroupDefineForm,
    NodeGroupEdit,
    NodeGroupInterfaceForeignDHCPForm,
    NodeGroupInterfaceForm,
    SSHKeyForm,
    TagForm,
    ZoneForm,
    )
from maasserver.forms_settings import (
    get_config_doc,
    get_config_form,
    validate_config_name,
    )
from maasserver.models import (
    BootImage,
    BootSource,
    BootSourceSelection,
    Config,
    DHCPLease,
    FileStorage,
    MACAddress,
    Network,
    Node,
    NodeGroup,
    NodeGroupInterface,
    SSHKey,
    Tag,
    Zone,
    )
from maasserver.models.nodeprobeddetails import (
    get_probed_details,
    get_single_probed_details,
    )
from maasserver.node_action import Commission
from maasserver.node_constraint_filter_forms import AcquireNodeForm
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    get_preseed_type_for,
    )
from maasserver.server_address import get_maas_facing_server_address
from maasserver.third_party_drivers import get_third_party_driver
from maasserver.utils import (
    absolute_reverse,
    build_absolute_uri,
    find_nodegroup,
    get_local_cluster_UUID,
    strip_domain,
    )
from maasserver.utils.orm import (
    get_first,
    get_one,
    )
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    NodeCommissionResult,
    )
import netaddr
from piston.emitters import JSONEmitter
from piston.handler import typemapper
from piston.utils import rc
from provisioningserver.kernel_opts import KernelParameters
from provisioningserver.power_schema import UNKNOWN_POWER_TYPE
import simplejson as json

# Node's fields exposed on the API.
DISPLAYED_NODE_FIELDS = (
    'system_id',
    'hostname',
    'owner',
    ('macaddress_set', ('mac_address',)),
    'architecture',
    'cpu_count',
    'memory',
    'storage',
    'status',
    'osystem',
    'distro_series',
    'netboot',
    'power_type',
    'tag_names',
    'ip_addresses',
    'routers',
    'zone',
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


class NodeHandler(OperationsHandler):
    """Manage an individual Node.

    The Node is identified by its system_id.
    """
    api_doc_section_name = "Node"

    create = None  # Disable create.
    model = Node
    fields = DISPLAYED_NODE_FIELDS

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

    def read(self, request, system_id):
        """Read a specific Node."""
        return Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)

    def update(self, request, system_id):
        """Update a specific Node.

        :param hostname: The new hostname for this node.
        :type hostname: unicode
        :param architecture: The new architecture for this node.
        :type architecture: unicode
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
        """
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        Form = get_node_edit_form(request.user)
        form = Form(data=request.data, instance=node)

        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    def delete(self, request, system_id):
        """Delete a specific Node."""
        node = Node.objects.get_node_or_404(
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
        """Shut down a node."""
        nodes = Node.objects.stop_nodes([system_id], request.user)
        if len(nodes) == 0:
            raise PermissionDenied(
                "You are not allowed to shut down this node.")
        return nodes[0]

    @operation(idempotent=False)
    def start(self, request, system_id):
        """Power up a node.

        :param user_data: If present, this blob of user-data to be made
            available to the nodes through the metadata service.
        :type user_data: base64-encoded unicode
        :param distro_series: If present, this parameter specifies the
            OS release the node will use.
        :type distro_series: unicode

        Ideally we'd have MIME multipart and content-transfer-encoding etc.
        deal with the encapsulation of binary data, but couldn't make it work
        with the framework in reasonable time so went for a dumb, manual
        encoding instead.
        """
        user_data = request.POST.get('user_data', None)
        series = request.POST.get('distro_series', None)
        license_key = request.POST.get('license_key', None)
        if user_data is not None:
            user_data = b64decode(user_data)
        if series is not None or license_key is not None:
            node = Node.objects.get_node_or_404(
                system_id=system_id, user=request.user,
                perm=NODE_PERMISSION.EDIT)
            Form = get_node_edit_form(request.user)
            form = Form(instance=node)
            if series is not None:
                form.set_distro_series(series=series)
            if license_key is not None:
                form.set_license_key(license_key=license_key)
            if form.is_valid():
                form.save()
            else:
                raise ValidationError(form.errors)
        try:
            nodes = Node.objects.start_nodes(
                [system_id], request.user, user_data=user_data)
        except StaticIPAddressExhaustion:
            # The API response should contain error text with the
            # system_id in it, as that is the primary API key to a node.
            raise StaticIPAddressExhaustion(
                "%s: Unable to allocate static IP due to address"
                " exhaustion." % system_id)
        if len(nodes) == 0:
            raise PermissionDenied(
                "You are not allowed to start up this node.")
        return nodes[0]

    @operation(idempotent=False)
    def release(self, request, system_id):
        """Release a node.  Opposite of `NodesHandler.acquire`."""
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        if node.status == NODE_STATUS.READY:
            # Nothing to do.  This may be a redundant retry, and the
            # postcondition is achieved, so call this success.
            pass
        elif node.status in [NODE_STATUS.ALLOCATED, NODE_STATUS.RESERVED]:
            node.release()
        else:
            raise NodeStateViolation(
                "Node cannot be released in its current state ('%s')."
                % node.display_status())
        return node

    @operation(idempotent=False)
    def commission(self, request, system_id):
        """Begin commissioning process for a node.

        A node in the 'ready', 'declared' or 'failed test' state may
        initiate a commissioning cycle where it is checked out and tested
        in preparation for transitioning to the 'ready' state. If it is
        already in the 'ready' state this is considered a re-commissioning
        process which is useful if commissioning tests were changed after
        it previously commissioned.
        """
        node = get_object_or_404(Node, system_id=system_id)
        form_class = get_action_form(user=request.user)
        form = form_class(
            node, data={NodeActionForm.input_name: Commission.name})
        if form.is_valid():
            node = form.save(allow_redirect=False)
            return node
        else:
            raise ValidationError(form.errors)

    @operation(idempotent=True)
    def details(self, request, system_id):
        """Obtain various system details.

        For example, LLDP and ``lshw`` XML dumps.

        Returns a ``{detail_type: xml, ...}`` map, where
        ``detail_type`` is something like "lldp" or "lshw".

        Note that this is returned as BSON and not JSON. This is for
        efficiency, but mainly because JSON can't do binary content
        without applying additional encoding like base-64.
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


def create_node(request):
    """Service an http request to create a node.

    The node will be in the Declared state.

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
    altered_query_data = request.data.copy()
    if given_arch and '/' in given_arch:
        if given_subarch:
            # Architecture with a '/' and a subarchitecture: error.
            raise ValidationError('Subarchitecture cannot be specified twice.')
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

    if 'nodegroup' not in altered_query_data:
        # If 'nodegroup' is not explicitely specified, get the origin of the
        # request to figure out which nodegroup the new node should be
        # attached to.
        if request.data.get('autodetect_nodegroup', None) is None:
            # We insist on this to protect command-line API users who
            # are manually enlisting nodes.  You can't use the origin's
            # IP address to indicate in which nodegroup the new node belongs.
            raise ValidationError(
                "'autodetect_nodegroup' must be specified if 'nodegroup' "
                "parameter missing")
        nodegroup = find_nodegroup(request)
        if nodegroup is not None:
            altered_query_data['nodegroup'] = nodegroup

    Form = get_node_create_form(request.user)
    form = Form(data=altered_query_data)
    if form.is_valid():
        node = form.save()
        node.use_fastpath_installer()
        # Hack in the power parameters here.
        store_node_power_parameters(node, request)
        return node
    else:
        raise ValidationError(form.errors)


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
        """Create a new Node.

        Adding a server to a MAAS puts it on a path that will wipe its disks
        and re-install its operating system.  In anonymous enlistment and when
        the enlistment is done by a non-admin, the node is held in the
        "Declared" state for approval by a MAAS admin.
        """
        # XXX 2014-02-11 bug=1278685
        # There's no documentation here on what parameters can be passed!

        # Note that request.autodetect_nodegroup is treated as a
        # boolean; its presence indicates True.
        return create_node(request)

    @operation(idempotent=True)
    def is_registered(self, request):
        """Returns whether or not the given MAC address is registered within
        this MAAS (and attached to a non-retired node).

        :param mac_address: The mac address to be checked.
        :type mac_address: unicode
        :return: 'true' or 'false'.
        :rtype: unicode
        """
        mac_address = get_mandatory_param(request.GET, 'mac_address')
        mac_addresses = MACAddress.objects.filter(mac_address=mac_address)
        mac_addresses = mac_addresses.exclude(node__status=NODE_STATUS.RETIRED)
        return mac_addresses.exists()

    @operation(idempotent=False)
    def accept(self, request):
        """Accept a node's enlistment: not allowed to anonymous users."""
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
        """Create a new Node.

        When a node has been added to MAAS by an admin MAAS user, it is
        ready for allocation to services running on the MAAS.
        The minimum data required is:
        architecture=<arch string> (e.g. "i386/generic")
        mac_addresses=<value> (e.g. "aa:bb:cc:dd:ee:ff")

        :param architecture: A string containing the architecture type of
            the node.
        :param mac_addresses: One or more MAC addresses for the node.
        :param hostname: A hostname. If not given, one will be generated.
        :param power_type: A power management type, if applicable (e.g.
            "virsh", "ipmi").
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
        existing_nodes = Node.objects.filter(system_id__in=system_ids)
        existing_ids = set(existing_nodes.values_list('system_id', flat=True))
        unknown_ids = system_ids - existing_ids
        if len(unknown_ids) > 0:
            raise MAASAPIBadRequest(
                "Unknown node(s): %s." % ', '.join(unknown_ids))

    @operation(idempotent=False)
    def accept(self, request):
        """Accept declared nodes into the MAAS.

        Nodes can be enlisted in the MAAS anonymously or by non-admin users,
        as opposed to by an admin.  These nodes are held in the Declared
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
        """
        system_ids = set(request.POST.getlist('nodes'))
        # Check the existence of these nodes first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        nodes = Node.objects.get_nodes(
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
        as opposed to by an admin.  These nodes are held in the Declared
        state; a MAAS admin must first verify the authenticity of these
        enlistments, and accept them.

        :return: Representations of any nodes that have their status changed
            by this call.  Thus, nodes that were already accepted are excluded
            from the result.
        """
        nodes = Node.objects.get_nodes(
            request.user, perm=NODE_PERMISSION.ADMIN)
        nodes = nodes.filter(status=NODE_STATUS.DECLARED)
        nodes = [node.accept_enlistment(request.user) for node in nodes]
        return filter(None, nodes)

    @operation(idempotent=False)
    def check_commissioning(self, request):
        """Check all commissioning nodes to see if they are taking too long.

        Anything that has been commissioning for longer than
        settings.COMMISSIONING_TIMEOUT is moved into the FAILED_TESTS status.
        """
        interval = timedelta(minutes=settings.COMMISSIONING_TIMEOUT)
        cutoff = datetime.now() - interval
        query = Node.objects.filter(
            status=NODE_STATUS.COMMISSIONING, updated__lte=cutoff)
        results = list(query)
        query.update(status=NODE_STATUS.FAILED_TESTS)
        # Note that Django doesn't call save() on updated nodes here,
        # but I don't think anything requires its effects anyway.
        return results

    @operation(idempotent=False)
    def release(self, request):
        """Release multiple nodes.

        This places the nodes back into the pool, ready to be reallocated.

        :param nodes: system_ids of the nodes which are to be released.
           (An empty list is acceptable).
        :return: The system_ids of any nodes that have their status
            changed by this call. Thus, nodes that were already released
            are excluded from the result.
        """
        system_ids = set(request.POST.getlist('nodes'))
         # Check the existence of these nodes first.
        self._check_system_ids_exist(system_ids)
        # Make sure that the user has the required permission.
        nodes = Node.objects.get_nodes(
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
            elif node.status in [NODE_STATUS.ALLOCATED, NODE_STATUS.RESERVED]:
                node.release()
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
        """List Nodes visible to the user, optionally filtered by criteria.

        :param hostname: An optional list of hostnames.  Only nodes with
            matching hostnames will be returned.
        :type hostname: iterable
        :param mac_address: An optional list of MAC addresses.  Only
            nodes with matching MAC addresses will be returned.
        :type mac_address: iterable
        :param id: An optional list of system ids.  Only nodes with
            matching system ids will be returned.
        :type id: iterable
        :param zone: An optional name for a physical zone. Only nodes in the
            zone will be returned.
        :type zone: unicode
        :param agent_name: An optional agent name.  Only nodes with
            matching agent names will be returned.
        :type agent_name: unicode
        """
        # Get filters from request.
        match_ids = get_optional_list(request.GET, 'id')
        match_macs = get_optional_list(request.GET, 'mac_address')
        if match_macs is not None:
            invalid_macs = [
                mac for mac in match_macs if MAC_RE.match(mac) is None]
            if len(invalid_macs) != 0:
                raise ValidationError(
                    "Invalid MAC address(es): %s" % ", ".join(invalid_macs))

        # Fetch nodes and apply filters.
        nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=match_ids)
        if match_macs is not None:
            nodes = nodes.filter(macaddress__mac_address__in=match_macs)
        match_hostnames = get_optional_list(request.GET, 'hostname')
        if match_hostnames is not None:
            nodes = nodes.filter(hostname__in=match_hostnames)
        match_zone_name = request.GET.get('zone', None)
        if match_zone_name is not None:
            nodes = nodes.filter(zone__name=match_zone_name)
        match_agent_name = request.GET.get('agent_name', None)
        if match_agent_name is not None:
            nodes = nodes.filter(agent_name=match_agent_name)

        # Prefetch related objects that are needed for rendering the result.
        nodes = nodes.prefetch_related('macaddress_set__node')
        nodes = nodes.prefetch_related('macaddress_set__ip_addresses')
        nodes = nodes.prefetch_related('tags')
        nodes = nodes.select_related('nodegroup')
        nodes = nodes.prefetch_related('nodegroup__dhcplease_set')
        nodes = nodes.prefetch_related('nodegroup__nodegroupinterface_set')
        nodes = nodes.prefetch_related('zone')
        return nodes.order_by('id')

    @operation(idempotent=True)
    def list_allocated(self, request):
        """Fetch Nodes that were allocated to the User/oauth token."""
        token = get_oauth_token(request)
        match_ids = get_optional_list(request.GET, 'id')
        nodes = Node.objects.get_allocated_visible_nodes(token, match_ids)
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
         """
        form = AcquireNodeForm(data=request.data)
        if form.is_valid():
            nodes = Node.objects.get_available_nodes_for_acquisition(
                request.user)
            nodes = form.filter_nodes(nodes)
            node = get_first(nodes)
            if node is None:
                constraints = form.describe_constraints()
                if constraints == '':
                    # No constraints.  That means no nodes at all were
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
                agent_name=agent_name)
            return node
        raise ValidationError(form.errors)

    @admin_method
    @operation(idempotent=False)
    def set_zone(self, request):
        """Assign multiple nodes to a physical zone at once.

        :param zone: Zone name.  If omitted, the zone is "none" and the nodes
            will be taken out of their physical zones.
        :param nodes: system_ids of the nodes whose zones are to be set.
           (An empty list is acceptable).
        """
        data = {
            'action': 'set_zone',
            'zone': request.data.get('zone'),
            'system_id': get_optional_list(request.data, 'nodes'),
        }
        form = BulkNodeActionForm(request.user, data=data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        form.save()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodeMacsHandler(OperationsHandler):
    """Manage MAC addresses for a given Node.

    This is where you manage the MAC addresses linked to a Node, including
    associating a new MAC address with the Node.

    The Node is identified by its system_id.
    """
    api_doc_section_name = "Node MAC addresses"
    update = delete = None

    def read(self, request, system_id):
        """Read all MAC addresses related to a Node."""
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.VIEW)

        return MACAddress.objects.filter(node=node).order_by('id')

    def create(self, request, system_id):
        """Create a MAC address for a specified Node."""
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.EDIT)
        mac = node.add_mac_address(request.data.get('mac_address', None))
        return mac

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('node_macs_handler', ['system_id'])


class NodeMacHandler(OperationsHandler):
    """Manage a Node MAC address.

    The MAC address object is identified by the system_id for the Node it
    is attached to, plus the MAC address itself.
    """
    api_doc_section_name = "Node MAC address"
    create = update = None
    fields = ('mac_address',)
    model = MACAddress

    def read(self, request, system_id, mac_address):
        """Read a MAC address related to a Node."""
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.VIEW)

        validate_mac(mac_address)
        return get_object_or_404(
            MACAddress, node=node, mac_address=mac_address)

    def delete(self, request, system_id, mac_address):
        """Delete a specific MAC address for the specified Node."""
        validate_mac(mac_address)
        node = Node.objects.get_node_or_404(
            user=request.user, system_id=system_id, perm=NODE_PERMISSION.EDIT)

        mac = get_object_or_404(MACAddress, node=node, mac_address=mac_address)
        mac.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, mac=None):
        node_system_id = "system_id"
        mac_address = "mac_address"
        if mac is not None:
            node_system_id = mac.node.system_id
            mac_address = mac.mac_address
        return ('node_mac_handler', [node_system_id, mac_address])


def get_file_by_name(handler, request):
    """Get a named file from the file storage.

    :param filename: The exact name of the file you want to get.
    :type filename: string
    :return: The file is returned in the response content.
    """
    filename = get_mandatory_param(request.GET, 'filename')
    try:
        db_file = FileStorage.objects.filter(filename=filename).latest('id')
    except FileStorage.DoesNotExist:
        raise MAASAPINotFound("File not found")
    return HttpResponse(db_file.content, status=httplib.OK)


def get_file_by_key(handler, request):
    """Get a file from the file storage using its key.

    :param key: The exact key of the file you want to get.
    :type key: string
    :return: The file is returned in the response content.
    """
    key = get_mandatory_param(request.GET, 'key')
    db_file = get_object_or_404(FileStorage, key=key)
    return HttpResponse(db_file.content, status=httplib.OK)


class AnonFilesHandler(AnonymousOperationsHandler):
    """Anonymous file operations.

    This is needed for Juju. The story goes something like this:

    - The Juju provider will upload a file using an "unguessable" name.

    - The name of this file (or its URL) will be shared with all the agents in
      the environment. They cannot modify the file, but they can access it
      without credentials.

    """
    create = read = update = delete = None

    get_by_name = operation(
        idempotent=True, exported_as='get')(get_file_by_name)
    get_by_key = operation(
        idempotent=True, exported_as='get_by_key')(get_file_by_key)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('files_handler', [])


# DISPLAYED_FILES_FIELDS_OBJECT is the list of fields used when dumping
# lists of FileStorage objects.
DISPLAYED_FILES_FIELDS = ('filename', 'anon_resource_uri')


def json_file_storage(stored_file, request):
    # Convert stored_file into a json object: use the same fields used
    # when serialising lists of object, plus the base64-encoded content.
    dict_representation = {
        fieldname: getattr(stored_file, fieldname)
        for fieldname in DISPLAYED_FILES_FIELDS
        }
    # Encode the content as base64.
    dict_representation['content'] = b64encode(
        getattr(stored_file, 'content'))
    dict_representation['resource_uri'] = reverse(
        'file_handler', args=[stored_file.filename])
    # Emit the json for this object manually because, no matter what the
    # piston documentation says, once a type is associated with a list
    # of fields by piston's typemapper mechanism, there is no way to
    # override that in a specific handler with 'fields' or 'exclude'.
    emitter = JSONEmitter(dict_representation, typemapper, None)
    stream = emitter.render(request)
    return stream


DISPLAY_SSHKEY_FIELDS = ("id", "key")


class SSHKeysHandler(OperationsHandler):
    """Manage the collection of all the SSH keys in this MAAS."""
    api_doc_section_name = "SSH Keys"

    create = read = update = delete = None

    @operation(idempotent=True)
    def list(self, request):
        """List all keys belonging to the requesting user."""
        return SSHKey.objects.filter(user=request.user)

    @operation(idempotent=False)
    def new(self, request):
        """Add a new SSH key to the requesting user's account.

        The request payload should contain the public SSH key data in form
        data whose name is "key".
        """
        form = SSHKeyForm(user=request.user, data=request.data)
        if form.is_valid():
            sshkey = form.save()
            emitter = JSONEmitter(
                sshkey, typemapper, None, DISPLAY_SSHKEY_FIELDS)
            stream = emitter.render(request)
            return HttpResponse(
                stream, mimetype='application/json; charset=utf-8',
                status=httplib.CREATED)
        else:
            raise ValidationError(form.errors)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('sshkeys_handler', [])


class SSHKeyHandler(OperationsHandler):
    """Manage an SSH key.

    SSH keys can be retrieved or deleted.
    """
    api_doc_section_name = "SSH Key"

    fields = DISPLAY_SSHKEY_FIELDS
    model = SSHKey
    create = update = None

    def read(self, request, keyid):
        """GET an SSH key."""
        key = get_object_or_404(SSHKey, id=keyid)
        return key

    @operation(idempotent=False)
    def delete(self, request, keyid):
        """DELETE an SSH key."""
        key = get_object_or_404(SSHKey, id=keyid)
        if key.user != request.user:
            return HttpResponse(
                "Can't delete a key you don't own.", status=httplib.FORBIDDEN)
        key.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, sshkey=None):
        keyid = "keyid"
        if sshkey is not None:
            keyid = sshkey.id
        return ('sshkey_handler', (keyid, ))


class FileHandler(OperationsHandler):
    """Manage a FileStorage object.

    The file is identified by its filename and owner.
    """
    api_doc_section_name = "File"
    model = FileStorage
    fields = DISPLAYED_FILES_FIELDS
    create = update = None

    def read(self, request, filename):
        """GET a FileStorage object as a json object.

        The 'content' of the file is base64-encoded."""
        try:
            stored_file = get_object_or_404(
                FileStorage, filename=filename, owner=request.user)
        except Http404:
            # In order to fix bug 1123986 we need to distinguish between
            # a 404 returned when the file is not present and a 404 returned
            # when the API endpoint is not present.  We do this by setting
            # a header: "Workaround: bug1123986".
            response = HttpResponse("Not Found", status=404)
            response["Workaround"] = "bug1123986"
            return response
        stream = json_file_storage(stored_file, request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    @operation(idempotent=False)
    def delete(self, request, filename):
        """Delete a FileStorage object."""
        stored_file = get_object_or_404(
            FileStorage, filename=filename, owner=request.user)
        stored_file.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, stored_file=None):
        filename = "filename"
        if stored_file is not None:
            filename = stored_file.filename
        return ('file_handler', (filename, ))


class FilesHandler(OperationsHandler):
    """Manage the collection of all the files in this MAAS."""
    api_doc_section_name = "Files"
    create = read = update = delete = None
    anonymous = AnonFilesHandler

    get_by_name = operation(
        idempotent=True, exported_as='get')(get_file_by_name)
    get_by_key = operation(
        idempotent=True, exported_as='get_by_key')(get_file_by_key)

    @operation(idempotent=False)
    def add(self, request):
        """Add a new file to the file storage.

        :param filename: The file name to use in the storage.
        :type filename: string
        :param file: Actual file data with content type
            application/octet-stream
        """
        filename = request.data.get("filename", None)
        if not filename:
            raise MAASAPIBadRequest("Filename not supplied")
        files = request.FILES
        if not files:
            raise MAASAPIBadRequest("File not supplied")
        if len(files) != 1:
            raise MAASAPIBadRequest("Exactly one file must be supplied")
        uploaded_file = files['file']

        # As per the comment in FileStorage, this ought to deal in
        # chunks instead of reading the file into memory, but large
        # files are not expected.
        FileStorage.objects.save_file(filename, uploaded_file, request.user)
        return HttpResponse('', status=httplib.CREATED)

    @operation(idempotent=True)
    def list(self, request):
        """List the files from the file storage.

        The returned files are ordered by file name and the content is
        excluded.

        :param prefix: Optional prefix used to filter out the returned files.
        :type prefix: string
        """
        prefix = request.GET.get("prefix", None)
        files = FileStorage.objects.filter(owner=request.user)
        if prefix is not None:
            files = files.filter(filename__startswith=prefix)
        files = files.order_by('filename')
        return files

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('files_handler', [])


def get_celery_credentials():
    """Return the credentials needed to connect to the broker."""
    celery_conf = app_or_default().conf
    return {
        'BROKER_URL': celery_conf.BROKER_URL,
    }


DISPLAYED_NODEGROUP_FIELDS = ('uuid', 'status', 'name', 'cluster_name')


def register_nodegroup(request, uuid):
    """Register a new nodegroup.

    If the master has not been configured yet, this nodegroup becomes the
    master.  In that situation, if the uuid is also the one configured locally
    (meaning that the cluster controller is running on the same host as this
    region controller), the new master is also automatically accepted.
    """
    master = NodeGroup.objects.ensure_master()

    # Has the master been configured yet?
    if master.uuid in ('master', ''):
        # No, the master is not yet configured.  No actual cluster
        # controllers have registered yet.  All we have is the
        # default placeholder.  We let the cluster controller that's
        # making this request take the master's place.
        update_instance = master
        local_uuid = get_local_cluster_UUID()
        is_local_cluster = (
            local_uuid is not None and
            uuid == local_uuid)
        if is_local_cluster:
            # It's the cluster controller that's running locally.
            # Auto-accept it.
            status = NODEGROUP_STATUS.ACCEPTED
        else:
            # It's a non-local cluster controller.  Keep it pending.
            status = NODEGROUP_STATUS.PENDING
    else:
        # It's a new regular cluster.  Create it, and keep it pending.
        update_instance = None
        status = NODEGROUP_STATUS.PENDING

    form = NodeGroupDefineForm(
        data=request.data, status=status, instance=update_instance)

    if not form.is_valid():
        raise ValidationError(form.errors)

    return form.save()


def compose_nodegroup_register_response(nodegroup, already_existed):
    """Return the right HTTP response to a `register` request.

    The response is based on the status of the `nodegroup` after registration,
    and whether it had already been registered before the call.

    If the nodegroup was accepted, this returns the cluster worker's Celery
    credentials.
    """
    if nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
        return get_celery_credentials()
    elif nodegroup.status == NODEGROUP_STATUS.REJECTED:
        raise PermissionDenied('Rejected cluster.')
    elif nodegroup.status == NODEGROUP_STATUS.PENDING:
        if already_existed:
            message = "Awaiting admin approval."
        else:
            message = "Cluster registered.  Awaiting admin approval."
        return HttpResponse(message, status=httplib.ACCEPTED)
    else:
        raise AssertionError("Unknown nodegroup status: %s", nodegroup.status)


class AnonNodeGroupsHandler(AnonymousOperationsHandler):
    """Anonymous access to NodeGroups."""
    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    @operation(idempotent=True)
    def list(self, request):
        """List of node groups."""
        return NodeGroup.objects.all()

    @classmethod
    def resource_uri(cls):
        return ('nodegroups_handler', [])

    @operation(idempotent=False)
    def refresh_workers(self, request):
        """Request an update of all node groups' configurations.

        This sends each node-group worker an update of its API credentials,
        OMAPI key, node-group name, and so on.

        Anyone can request this (for example, a bootstrapping worker that
        does not know its node-group name or API credentials yet) but the
        information will be sent only to the known workers.
        """
        NodeGroup.objects.refresh_workers()
        return HttpResponse("Sending worker refresh.", status=httplib.OK)

    @operation(idempotent=False)
    def register(self, request):
        """Register a new cluster controller.

        This method will use HTTP return codes to indicate the success of the
        call:

        - 200 (OK): the cluster controller has been accepted.  The response
          will contain the RabbitMQ credentials in JSON format, e.g.:
          '{"BROKER_URL" = "amqp://guest:guest@localhost:5672//"}'
        - 202 (Accepted): the cluster controller has been registered.  It is
          now pending acceptance by an administrator.  Please try again later.
        - 403 (Forbidden): this cluster controller has been rejected.

        :param uuid: The cluster's UUID.
        :type name: unicode
        :param name: The cluster's name.
        :type name: unicode
        :param interfaces: The cluster controller's network interfaces.
        :type interfaces: JSON string containing a list of dictionaries with
            the data to initialize the interfaces.
            e.g.: '[{"ip_range_high": "192.168.168.254",
            "ip_range_low": "192.168.168.1", "broadcast_ip":
            "192.168.168.255", "ip": "192.168.168.18", "subnet_mask":
            "255.255.255.0", "router_ip": "192.168.168.1", "interface":
            "eth0"}]'
        """
        uuid = get_mandatory_param(request.data, 'uuid')
        nodegroup = get_one(NodeGroup.objects.filter(uuid=uuid))
        already_existed = (nodegroup is not None)
        if already_existed:
            if nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
                # This cluster controller has been accepted.  Use the
                # information in the request to update the MAAS URL we will
                # send it from now on.
                update_nodegroup_maas_url(nodegroup, request)
        else:
            nodegroup = register_nodegroup(request, uuid)

        return compose_nodegroup_register_response(nodegroup, already_existed)


def update_nodegroup_maas_url(nodegroup, request):
    """Update `nodegroup.maas_url` from the given `request`.

    Only update `nodegroup.maas_url` if the hostname part is not 'localhost'
    (i.e. the default value used when the master nodegroup connects).
    """
    path = request.META["SCRIPT_NAME"]
    maas_url = build_absolute_uri(request, path)
    server_host = urlparse(maas_url).hostname
    if server_host != 'localhost':
        nodegroup.maas_url = maas_url
        nodegroup.save()


def update_mac_cluster_interfaces(leases, cluster):
    """Calculate and store which interface a MAC is attached to."""
    interface_ranges = {}
    for interface in cluster.nodegroupinterface_set.all():
        ip_range = netaddr.IPRange(
            interface.ip_range_low, interface.ip_range_high)
        interface_ranges[interface] = ip_range
    for ip, mac in leases.items():
        try:
            mac_address = MACAddress.objects.get(mac_address=mac)
        except MACAddress.DoesNotExist:
            # Silently ignore MAC addresses that we don't know about.
            continue
        for interface, ip_range in interface_ranges.items():
            if netaddr.IPAddress(ip) in ip_range:
                mac_address.cluster_interface = interface
                mac_address.save()
                # Cheap optimisation. No other interfaces will match, so
                # break out of the loop.
                break


class NodeGroupsHandler(OperationsHandler):
    """Manage the collection of all the nodegroups in this MAAS."""

    api_doc_section_name = "Nodegroups"
    anonymous = AnonNodeGroupsHandler
    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    @operation(idempotent=True)
    def list(self, request):
        """List nodegroups."""
        return NodeGroup.objects.all()

    @admin_method
    @operation(idempotent=False)
    def accept(self, request):
        """Accept nodegroup enlistment(s).

        :param uuid: The UUID (or list of UUIDs) of the nodegroup(s) to accept.
        :type name: unicode (or list of unicodes)

        This method is reserved to admin users.
        """
        uuids = request.data.getlist('uuid')
        for uuid in uuids:
            nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
            nodegroup.accept()
        return HttpResponse("Nodegroup(s) accepted.", status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request):
        """Import the boot images on all the accepted cluster controllers."""
        NodeGroup.objects.import_boot_images_accepted_clusters()
        return HttpResponse(
            "Import of boot images started on all cluster controllers",
            status=httplib.OK)

    @operation(idempotent=True)
    def describe_power_types(self, request):
        """Query all the cluster controllers for power information.

        :return: a list of dicts that describe the power types in this format.
        """
        return get_all_power_types_from_clusters()

    @admin_method
    @operation(idempotent=False)
    def reject(self, request):
        """Reject nodegroup enlistment(s).

        :param uuid: The UUID (or list of UUIDs) of the nodegroup(s) to reject.
        :type name: unicode (or list of unicodes)

        This method is reserved to admin users.
        """
        uuids = request.data.getlist('uuid')
        for uuid in uuids:
            nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
            nodegroup.reject()
        return HttpResponse("Nodegroup(s) rejected.", status=httplib.OK)

    @classmethod
    def resource_uri(cls):
        return ('nodegroups_handler', [])


def check_nodegroup_access(request, nodegroup):
    """Validate API access by worker for `nodegroup`.

    This supports a nodegroup worker accessing its nodegroup object on
    the API.  If the request is done by anyone but the worker for this
    particular nodegroup, the function raises :class:`PermissionDenied`.
    """
    try:
        key = extract_oauth_key(request)
    except Unauthorized as e:
        raise PermissionDenied(unicode(e))

    if key != nodegroup.api_key:
        raise PermissionDenied(
            "Only allowed for the %r worker." % nodegroup.name)


class NodeGroupHandler(OperationsHandler):
    """Manage a NodeGroup.

    NodeGroup is the internal name for a cluster.

    The NodeGroup is identified by its UUID, a random identifier that looks
    something like:

        5977f6ab-9160-4352-b4db-d71a99066c4f

    Each NodeGroup has its own uuid.
    """
    api_doc_section_name = "Nodegroup"

    create = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    def read(self, request, uuid):
        """GET a node group."""
        return get_object_or_404(NodeGroup, uuid=uuid)

    @classmethod
    def resource_uri(cls, nodegroup=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        return ('nodegroup_handler', [uuid])

    @admin_method
    def update(self, request, uuid):
        """Update a specific cluster.

        :param name: The new DNS name for this cluster.
        :type name: unicode
        :param cluster_name: The new name for this cluster.
        :type cluster_name: unicode
        :param status: The new status for this cluster (see
            vocabulary `NODEGROUP_STATUS`).
        :type status: int
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        form = NodeGroupEdit(instance=nodegroup, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    @operation(idempotent=False)
    def update_leases(self, request, uuid):
        """Submit latest state of DHCP leases within the cluster.

        The cluster controller calls this periodically to tell the region
        controller about the IP addresses it manages.
        """
        leases = get_mandatory_param(request.data, 'leases')
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        check_nodegroup_access(request, nodegroup)
        leases = json.loads(leases)
        DHCPLease.objects.update_leases(nodegroup, leases)
        update_mac_cluster_interfaces(leases, nodegroup)
        return HttpResponse("Leases updated.", status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def import_boot_images(self, request, uuid):
        """Import the pxe files on this cluster controller."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        nodegroup.import_boot_images()
        return HttpResponse(
            "Import of boot images started on cluster %r" % nodegroup.uuid,
            status=httplib.OK)

    @operation(idempotent=True)
    def list_nodes(self, request, uuid):
        """Get the list of node ids that are part of this group."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        nodes = Node.objects.filter(nodegroup=nodegroup).only('system_id')
        return [node.system_id for node in nodes]

    # details is actually idempotent, however:
    # a) We expect to get a list of system_ids which is quite long (~100 ids,
    #    each 40 bytes, is 4000 bytes), which is a bit too long for a URL.
    # b) MAASClient.get() just uses urlencode(params) but urlencode ends up
    #    just stringifying the list and encoding that, which transforms the
    #    list of ids into something unusable. .post() does the right thing.
    @operation(idempotent=False)
    def details(self, request, uuid):
        """Obtain various system details for each node specified.

        For example, LLDP and ``lshw`` XML dumps.

        Returns a ``{system_id: {detail_type: xml, ...}, ...}`` map,
        where ``detail_type`` is something like "lldp" or "lshw".

        :param system_ids: System ids of nodes for which to get system details.

        Note that this is returned as BSON and not JSON. This is for
        efficiency, but mainly because JSON can't do binary content
        without applying additional encoding like base-64.

        For security purposes:

        a) Requests are only fulfilled for the worker assigned to the
           nodegroup.
        b) Requests for nodes that are not part of the nodegroup are
           just ignored.

        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        system_ids = get_list_from_dict_or_multidict(
            request.data, 'system_ids', [])
        # Filter out system IDs that are not in this nodegroup.
        system_ids = Node.objects.filter(
            system_id__in=system_ids, nodegroup=nodegroup)
        # Unwrap the values_list.
        system_ids = {
            system_id for (system_id,) in
            system_ids.values_list('system_id')
        }
        # Obtain details and prepare for BSON encoding.
        details = get_probed_details(system_ids)
        for detail in details.itervalues():
            for name, value in detail.iteritems():
                if value is not None:
                    detail[name] = bson.Binary(value)
        return HttpResponse(
            bson.BSON.encode(details),
            # Not sure what media type to use here.
            content_type='application/bson')

    @operation(idempotent=False)
    def report_download_progress(self, request, uuid):
        """Report progress of a download.

        Cluster controllers can call this to update the region controller on
        file downloads they need to perform, such as kernels and initrd files.
        This gives the administrator insight into what downloads are in
        progress, how well downloads are going, and what failures may have
        occurred.

        A file is identified by an arbitrary name, which must be consistent.
        It could be a URL, or a filesystem path, or even a symbolic name that
        the cluster controller makes up.  A cluster controller can download
        the same file many times over, but not simultaneously.

        Before downloading a file, a cluster controller first reports progress
        without the `bytes_downloaded` parameter.  It may optionally report
        progress while downloading, passing the number of bytes downloaded
        so far.  Finally, if the download succeeded, it should report one final
        time with the full number of bytes downloaded.

        If the download fails, the cluster controller should report progress
        with an error string (and either the number of bytes that were
        successfully downloaded, or zero).

        Progress reports should include the file's size, if known.  The final
        report after a successful download must include the size.

        :param filename: Arbitrary identifier for the file being downloaded.
        :type filename: unicode
        :param size: Optional size of the file, in bytes.  Must be passed at
            least once, though it can still be passed on subsequent calls.  If
            file size is not known, pass it at the end when reporting
            successful completion.  Do not change the size once given.
        :param bytes_downloaded: Number of bytes that have been successfully
            downloaded.  Cannot exceed `size`, if known.  This parameter must
            be omitted from the initial progress report before download starts,
            and must be included for all subsequent progress reports for that
            download.
        :type bytes_downloaded: int
        :param error: Optional error string.  A download that has submitted an
            error with its last progress report is considered to have failed.
        :type error: unicode
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        check_nodegroup_access(request, nodegroup)
        filename = get_mandatory_param(request.data, 'filename')
        bytes_downloaded = request.data.get('bytes_downloaded', None)

        download = DownloadProgressForm.get_download(
            nodegroup, filename, bytes_downloaded)

        if 'size' not in request.data:
            # No size given.  If one was specified previously, use that.
            request.data['size'] = download.size

        form = DownloadProgressForm(data=request.data, instance=download)
        if not form.is_valid():
            raise ValidationError(form.errors)
        form.save()

        return HttpResponse(status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_hardware(self, request, uuid):
        """Add special hardware types.

        :param model: The type of special hardware, 'seamicro15k' and
            'virsh' is supported.
        :type model: unicode

        The following are only required if you are probing a seamicro15k:

        :param mac: The MAC of the seamicro15k chassis.
        :type mac: unicode
        :param username: The username for the chassis.
        :type username: unicode
        :param password: The password for the chassis.
        :type password: unicode

        The following are optional if you are probing a seamicro15k:

        :param power_control: The power_control to use, either ipmi (default)
            or restapi.
        :type power_control: unicode

        The following are only required if you are probing a virsh:

        :param power_address: The connection string to virsh.
        :type power_address: unicode

        The following are optional if you are probing a virsh:

        :param power_pass: The password to use, when qemu+ssh is given as a
            connection string and ssh key authentication is not being used.
        :type power_pass: unicode
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        model = get_mandatory_param(request.data, 'model')
        if model == 'seamicro15k':
            mac = get_mandatory_param(request.data, 'mac')
            username = get_mandatory_param(request.data, 'username')
            password = get_mandatory_param(request.data, 'password')
            power_control = get_optional_param(
                request.data, 'power_control', default='ipmi',
                validator=validators.OneOf(['ipmi', 'restapi', 'restapi2']))

            nodegroup.add_seamicro15k(
                mac, username, password, power_control=power_control)
        elif model == 'powerkvm' or model == 'virsh':
            poweraddr = get_mandatory_param(request.data, 'power_address')
            password = get_optional_param(
                request.data, 'power_pass', default=None)

            nodegroup.add_virsh(poweraddr, password=password)
        else:
            return HttpResponse(status=httplib.BAD_REQUEST)

        return HttpResponse(status=httplib.OK)

    @admin_method
    @operation(idempotent=False)
    def probe_and_enlist_ucsm(self, request, uuid):
        """Add the nodes from a Cisco UCS Manager.

        :param : The URL of the UCS Manager API.
        :type url: unicode
        :param username: The username for the API.
        :type username: unicode
        :param password: The password for the API.
        :type password: unicode

        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)

        url = get_mandatory_param(request.data, 'url')
        username = get_mandatory_param(request.data, 'username')
        password = get_mandatory_param(request.data, 'password')

        nodegroup.enlist_nodes_from_ucsm(url, username, password)

        return HttpResponse(status=httplib.OK)

DISPLAYED_NODEGROUPINTERFACE_FIELDS = (
    'ip', 'management', 'interface', 'subnet_mask',
    'broadcast_ip', 'ip_range_low', 'ip_range_high',
    'static_ip_range_low', 'static_ip_range_high',
    )


class NodeGroupInterfacesHandler(OperationsHandler):
    """Manage the collection of all the NodeGroupInterfaces in this MAAS.

    A NodeGroupInterface is a network interface attached to a cluster
    controller, with its network properties.
    """
    api_doc_section_name = "Nodegroup interfaces"

    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUPINTERFACE_FIELDS

    @operation(idempotent=True)
    def list(self, request, uuid):
        """List of NodeGroupInterfaces of a NodeGroup."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        return NodeGroupInterface.objects.filter(nodegroup=nodegroup)

    @operation(idempotent=False)
    def new(self, request, uuid):
        """Create a new NodeGroupInterface for this NodeGroup.

        :param ip: Static IP of the interface.
        :type ip: unicode (IP Address)
        :param interface: Name of the interface.
        :type interface: unicode
        :param management: The service(s) MAAS should manage on this interface.
        :type management: Vocabulary `NODEGROUPINTERFACE_MANAGEMENT`
        :param subnet_mask: Subnet mask, e.g. 255.0.0.0.
        :type subnet_mask: unicode (IP Address)
        :param broadcast_ip: Broadcast address for this subnet.
        :type broadcast_ip: unicode (IP Address)
        :param router_ip: Address of default gateway.
        :type router_ip: unicode (IP Address)
        :param ip_range_low: Lowest dynamic IP address to assign to clients.
        :type ip_range_low: unicode (IP Address)
        :param ip_range_high: Highest dynamic IP address to assign to clients.
        :type ip_range_high: unicode (IP Address)
        :param static_ip_range_low: Lowest static IP address to assign to
            clients.
        :type static_ip_range_low: unicode (IP Address)
        :param static_ip_range_high: Highest static IP address to assign to
            clients.
        :type static_ip_range_high: unicode (IP Address)
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        instance = NodeGroupInterface(nodegroup=nodegroup)
        form = NodeGroupInterfaceForm(request.data, instance=instance)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    @classmethod
    def resource_uri(cls, nodegroup=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        return ('nodegroupinterfaces_handler', [uuid])


class NodeGroupInterfaceHandler(OperationsHandler):
    """Manage a NodeGroupInterface.

    A NodeGroupInterface is identified by the uuid for its NodeGroup, and
    the name of the network interface it represents: "eth0" for example.
    """
    api_doc_section_name = "Nodegroup interface"

    create = delete = None
    fields = DISPLAYED_NODEGROUPINTERFACE_FIELDS

    def get_interface(self, request, uuid, interface):
        """Return the :class:`NodeGroupInterface` indicated by the request.

        Will check for not-found errors, as well as the user's permission to
        perform the request's operation on the nodegroup.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        nodegroupinterface = get_object_or_404(
            NodeGroupInterface, nodegroup=nodegroup, interface=interface)
        return nodegroupinterface

    def read(self, request, uuid, interface):
        """List of NodeGroupInterfaces of a NodeGroup."""
        return self.get_interface(request, uuid, interface)

    def update(self, request, uuid, interface):
        """Update a specific NodeGroupInterface.

        :param ip: Static IP of the interface.
        :type ip: unicode (IP Address)
        :param interface: Name of the interface.
        :type interface: unicode
        :param management: The service(s) MAAS should manage on this interface.
        :type management: Vocabulary `NODEGROUPINTERFACE_MANAGEMENT`
        :param subnet_mask: Subnet mask, e.g. 255.0.0.0.
        :type subnet_mask: unicode (IP Address)
        :param broadcast_ip: Broadcast address for this subnet.
        :type broadcast_ip: unicode (IP Address)
        :param router_ip: Address of default gateway.
        :type router_ip: unicode (IP Address)
        :param ip_range_low: Lowest dynamic IP address to assign to clients.
        :type ip_range_low: unicode (IP Address)
        :param ip_range_high: Highest dynamic IP address to assign to clients.
        :type ip_range_high: unicode (IP Address)
        :param static_ip_range_low: Lowest static IP address to assign to
            clients.
        :type static_ip_range_low: unicode (IP Address)
        :param static_ip_range_high: Highest static IP address to assign to
            clients.
        :type static_ip_range_high: unicode (IP Address)
        """
        nodegroupinterface = self.get_interface(request, uuid, interface)
        form = NodeGroupInterfaceForm(
            request.data, instance=nodegroupinterface)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    def delete(self, request, uuid, interface):
        """Delete a specific NodeGroupInterface."""
        nodegroupinterface = self.get_interface(request, uuid, interface)
        nodegroupinterface.delete()
        return rc.DELETED

    @operation(idempotent=False)
    def report_foreign_dhcp(self, request, uuid, interface):
        """Report the result of a probe for foreign DHCP servers.

        Cluster controllers probe for DHCP servers not managed by MAAS, and
        call this method to report their findings.

        :param foreign_dhcp_ip: New value for the foreign DHCP server found
            during the last probe.  Leave blank if none were found.
        """
        foreign_dhcp_ip = get_mandatory_param(request.data, 'foreign_dhcp_ip')
        nodegroupinterface = self.get_interface(request, uuid, interface)

        form = NodeGroupInterfaceForeignDHCPForm(
            {'foreign_dhcp_ip': foreign_dhcp_ip}, instance=nodegroupinterface)
        if not form.is_valid():
            raise ValidationError(form.errors)
        else:
            return form.save()

    @classmethod
    def resource_uri(cls, nodegroup=None, interface=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        if interface is None:
            interface_name = 'interface'
        else:
            interface_name = interface.interface
        return ('nodegroupinterface_handler', [uuid, interface_name])


class AccountHandler(OperationsHandler):
    """Manage the current logged-in user."""
    api_doc_section_name = "Logged-in user"
    create = read = update = delete = None

    @operation(idempotent=False)
    def create_authorisation_token(self, request):
        """Create an authorisation OAuth token and OAuth consumer.

        :return: a json dict with three keys: 'token_key',
            'token_secret' and 'consumer_key' (e.g.
            {token_key: 's65244576fgqs', token_secret: 'qsdfdhv34',
            consumer_key: '68543fhj854fg'}).
        :rtype: string (json)

        """
        profile = request.user.get_profile()
        consumer, token = profile.create_authorisation_token()
        return {
            'token_key': token.key, 'token_secret': token.secret,
            'consumer_key': consumer.key,
            }

    @operation(idempotent=False)
    def delete_authorisation_token(self, request):
        """Delete an authorisation OAuth token and the related OAuth consumer.

        :param token_key: The key of the token to be deleted.
        :type token_key: unicode
        """
        profile = request.user.get_profile()
        token_key = get_mandatory_param(request.data, 'token_key')
        profile.delete_authorisation_token(token_key)
        return rc.DELETED

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('account_handler', [])


class TagHandler(OperationsHandler):
    """Manage a Tag.

    Tags are properties that can be associated with a Node and serve as
    criteria for selecting and allocating nodes.

    A Tag is identified by its name.
    """
    api_doc_section_name = "Tag"
    create = None
    model = Tag
    fields = (
        'name',
        'definition',
        'comment',
        'kernel_opts',
        )

    def read(self, request, name):
        """Read a specific Tag"""
        return Tag.objects.get_tag_or_404(name=name, user=request.user)

    def update(self, request, name):
        """Update a specific Tag.

        :param name: The name of the Tag to be created. This should be a short
            name, and will be used in the URL of the tag.
        :param comment: A long form description of what the tag is meant for.
            It is meant as a human readable description of the tag.
        :param definition: An XPATH query that will be evaluated against the
            hardware_details stored for all nodes (output of `lshw -xml`).
        """
        tag = Tag.objects.get_tag_or_404(
            name=name, user=request.user, to_edit=True)
        form = TagForm(request.data, instance=tag)
        if form.is_valid():
            try:
                new_tag = form.save(commit=False)
                new_tag.save()
                form.save_m2m()
            except DatabaseError as e:
                raise ValidationError(e)
            return new_tag
        else:
            raise ValidationError(form.errors)

    def delete(self, request, name):
        """Delete a specific Tag."""
        tag = Tag.objects.get_tag_or_404(
            name=name, user=request.user, to_edit=True)
        tag.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def nodes(self, request, name):
        """Get the list of nodes that have this tag."""
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user)
        return Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, from_nodes=tag.node_set.all())

    def _get_nodes_for(self, request, param, nodegroup):
        system_ids = get_list_from_dict_or_multidict(request.data, param)
        if system_ids:
            nodes = Node.objects.filter(system_id__in=system_ids)
            if nodegroup is not None:
                nodes = nodes.filter(nodegroup=nodegroup)
        else:
            nodes = Node.objects.none()
        return nodes

    @operation(idempotent=False)
    def rebuild(self, request, name):
        """Manually trigger a rebuild the tag <=> node mapping.

        This is considered a maintenance operation, which should normally not
        be necessary. Adding nodes or updating a tag's definition should
        automatically trigger the appropriate changes.
        """
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user,
                                         to_edit=True)
        tag.populate_nodes()
        return {'rebuilding': tag.name}

    @operation(idempotent=False)
    def update_nodes(self, request, name):
        """Add or remove nodes being associated with this tag.

        :param add: system_ids of nodes to add to this tag.
        :param remove: system_ids of nodes to remove from this tag.
        :param definition: (optional) If supplied, the definition will be
            validated against the current definition of the tag. If the value
            does not match, then the update will be dropped (assuming this was
            just a case of a worker being out-of-date)
        :param nodegroup: A uuid of a nodegroup being processed. This value is
            optional. If not supplied, the requester must be a superuser. If
            supplied, then the requester must be the worker associated with
            that nodegroup, and only nodes that are part of that nodegroup can
            be updated.
        """
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user)
        nodegroup = None
        if not request.user.is_superuser:
            uuid = request.data.get('nodegroup', None)
            if uuid is None:
                raise PermissionDenied(
                    'Must be a superuser or supply a nodegroup')
            nodegroup = get_one(NodeGroup.objects.filter(uuid=uuid))
            check_nodegroup_access(request, nodegroup)
        definition = request.data.get('definition', None)
        if definition is not None and tag.definition != definition:
            return HttpResponse(
                "Definition supplied '%s' "
                "doesn't match current definition '%s'"
                % (definition, tag.definition),
                status=httplib.CONFLICT)
        nodes_to_add = self._get_nodes_for(request, 'add', nodegroup)
        tag.node_set.add(*nodes_to_add)
        nodes_to_remove = self._get_nodes_for(request, 'remove', nodegroup)
        tag.node_set.remove(*nodes_to_remove)
        return {
            'added': nodes_to_add.count(),
            'removed': nodes_to_remove.count()
            }

    @classmethod
    def resource_uri(cls, tag=None):
        # See the comment in NodeHandler.resource_uri
        tag_name = 'name'
        if tag is not None:
            tag_name = tag.name
        return ('tag_handler', (tag_name, ))


class TagsHandler(OperationsHandler):
    """Manage the collection of all the Tags in this MAAS."""
    api_doc_section_name = "Tags"
    create = read = update = delete = None

    @operation(idempotent=False)
    def new(self, request):
        """Create a new Tag.

        :param name: The name of the Tag to be created. This should be a short
            name, and will be used in the URL of the tag.
        :param comment: A long form description of what the tag is meant for.
            It is meant as a human readable description of the tag.
        :param definition: An XPATH query that will be evaluated against the
            hardware_details stored for all nodes (output of `lshw -xml`).
        :param kernel_opts: Can be None. If set, nodes associated with this tag
            will add this string to their kernel options when booting. The
            value overrides the global 'kernel_opts' setting. If more than one
            tag is associated with a node, the one with the lowest alphabetical
            name will be picked (eg 01-my-tag will be taken over 99-tag-name).
        """
        if not request.user.is_superuser:
            raise PermissionDenied()
        form = TagForm(request.data)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    @operation(idempotent=True)
    def list(self, request):
        """List Tags.

        Get a listing of all tags that are currently defined.
        """
        return Tag.objects.all()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('tags_handler', [])


class MaasHandler(OperationsHandler):
    """Manage the MAAS server."""
    api_doc_section_name = "MAAS server"
    create = read = update = delete = None

    @operation(idempotent=False)
    def set_config(self, request):
        """Set a config value.

        :param name: The name of the config item to be set.
        :type name: unicode
        :param value: The value of the config item to be set.
        :type value: json object

        %s
        """
        name = get_mandatory_param(
            request.data, 'name', validators.String(min=1))
        value = get_mandatory_param(request.data, 'value')
        form = get_config_form(name, {name: value})
        if not form.is_valid():
            raise ValidationError(form.errors)
        form.save()
        return rc.ALL_OK

    # Populate the docstring with the dynamically-generated documentation
    # about the available configuration items.
    set_config.__doc__ %= get_config_doc(indentation=8)

    @operation(idempotent=True)
    def get_config(self, request):
        """Get a config value.

        :param name: The name of the config item to be retrieved.
        :type name: unicode

        %s
        """
        name = get_mandatory_param(request.GET, 'name')
        validate_config_name(name)
        value = Config.objects.get_config(name)
        return HttpResponse(json.dumps(value), content_type='application/json')

    # Populate the docstring with the dynamically-generated documentation
    # about the available configuration items.
    get_config.__doc__ %= get_config_doc(indentation=8)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('maas_handler', [])


class UsersHandler(OperationsHandler):
    """Manage the user accounts of this MAAS."""
    api_doc_section_name = "Users"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('users_handler', [])

    def read(self, request):
        """List users."""
        return User.objects.all().order_by('username')

    @admin_method
    def create(self, request):
        """Create a MAAS user account.

        This is not safe: the password is sent in plaintext.  Avoid it for
        production, unless you are confident that you can prevent eavesdroppers
        from observing the request.

        :param username: Identifier-style username for the new user.
        :type username: unicode
        :param email: Email address for the new user.
        :type email: unicode
        :param password: Password for the new user.
        :type password: unicode
        :param is_superuser: Whether the new user is to be an administrator.
        :type is_superuser: bool ('0' for False, '1' for True)
        """
        username = get_mandatory_param(request.data, 'username')
        email = get_mandatory_param(request.data, 'email')
        password = get_mandatory_param(request.data, 'password')
        is_superuser = extract_bool(
            get_mandatory_param(request.data, 'is_superuser'))

        if is_superuser:
            return User.objects.create_superuser(
                username=username, password=password, email=email)
        else:
            return User.objects.create_user(
                username=username, password=password, email=email)


class UserHandler(OperationsHandler):
    """Manage a user account."""
    api_doc_section_name = "User"
    create = update = delete = None

    model = User
    fields = (
        'username',
        'email',
        'is_superuser',
        )

    def read(self, request, username):
        return get_object_or_404(User, username=username)


# MAAS capabilities. See docs/capabilities.rst for documentation.
CAP_NETWORKS_MANAGEMENT = 'networks-management'

API_CAPABILITIES_LIST = [
    CAP_NETWORKS_MANAGEMENT,
]


class VersionHandler(AnonymousOperationsHandler):
    """Information about this MAAS instance.

    This returns a JSON dictionary with information about this
    MAAS instance.
    {
        'capabilities': ['capability1', 'capability2', ...]
    }
    """
    api_doc_section_name = "MAAS version"
    create = update = delete = None

    def read(self, request):
        version_info = {
            'capabilities': API_CAPABILITIES_LIST,
        }
        return HttpResponse(
            version_info, mimetype='application/json; charset=utf-8',
            status=httplib.OK)


# Title section for the API documentation.  Matches in style, format,
# etc. whatever render_api_docs() produces, so that you can concatenate
# the two.
api_doc_title = dedent("""
    .. _region-controller-api:

    ========
    MAAS API
    ========
    """.lstrip('\n'))


def render_api_docs():
    """Render ReST documentation for the REST API.

    This module's docstring forms the head of the documentation; details of
    the API methods follow.

    :return: Documentation, in ReST, for the API.
    :rtype: :class:`unicode`
    """
    from maasserver import urls_api as urlconf

    module = sys.modules[__name__]
    output = StringIO()
    line = partial(print, file=output)

    line(getdoc(module))
    line()
    line()
    line('Operations')
    line('----------')
    line()

    resources = find_api_resources(urlconf)
    for doc in generate_api_docs(resources):
        uri_template = doc.resource_uri_template
        exports = doc.handler.exports.items()
        # Derive a section title from the name of the handler class.
        section_name = doc.handler.api_doc_section_name
        line(section_name)
        line('=' * len(section_name))
        line(doc.handler.__doc__)
        line()
        line()
        for (http_method, op), function in sorted(exports):
            line("``%s %s``" % (http_method, uri_template), end="")
            if op is not None:
                line(" ``op=%s``" % op)
            line()
            docstring = getdoc(function)
            if docstring is not None:
                for docline in docstring.splitlines():
                    line("  ", docline, sep="")
                line()

    line()
    line()
    line(generate_power_types_doc())

    return output.getvalue()


def reST_to_html_fragment(a_str):
    parts = core.publish_parts(source=a_str, writer_name='html')
    return parts['body_pre_docinfo'] + parts['fragment']


def api_doc(request):
    """Get ReST documentation for the REST API."""
    # Generate the documentation and keep it cached.  Note that we can't do
    # that at the module level because the API doc generation needs Django
    # fully initialized.
    return render_to_response(
        'maasserver/api_doc.html',
        {'doc': reST_to_html_fragment(render_api_docs())},
        context_instance=RequestContext(request))


def get_boot_purpose(node, osystem, arch, subarch, series, label):
    """Return a suitable "purpose" for this boot, e.g. "install"."""
    # XXX: allenap bug=1031406 2012-07-31: The boot purpose is still in
    # flux. It may be that there will just be an "ephemeral" environment and
    # an "install" environment, and the differing behaviour between, say,
    # enlistment and commissioning - both of which will use the "ephemeral"
    # environment - will be governed by varying the preseed or PXE
    # configuration.
    if node is None:
        # This node is enlisting, for which we use a commissioning image.
        return "commissioning"
    elif node.status == NODE_STATUS.COMMISSIONING:
        # It is commissioning.
        return "commissioning"
    elif node.status == NODE_STATUS.ALLOCATED:
        # Install the node if netboot is enabled, otherwise boot locally.
        if node.netboot:
            preseed_type = get_preseed_type_for(node)
            if preseed_type == PRESEED_TYPE.CURTIN:
                return "xinstall"
            else:
                return "install"
        else:
            return "local"  # TODO: Investigate.
    else:
        # Just poweroff? TODO: Investigate. Perhaps even send an IPMI signal
        # to turn off power.
        return "poweroff"


def get_node_from_mac_string(mac_string):
    """Get a Node object from a MAC address string.

    Returns a Node object or None if no node with the given MAC address exists.

    :param mac_string: MAC address string in the form "12-34-56-78-9a-bc"
    :return: Node object or None
    """
    if mac_string is None:
        return None
    macaddress = get_one(MACAddress.objects.filter(mac_address=mac_string))
    return macaddress.node if macaddress else None


def find_nodegroup_for_pxeconfig_request(request):
    """Find the nodegroup responsible for a `pxeconfig` request.

    Looks for the `cluster_uuid` parameter in the request.  If there is
    none, figures it out based on the requesting IP as a compatibility
    measure.  In that case, the result may be incorrect.
    """
    uuid = request.GET.get('cluster_uuid', None)
    if uuid is None:
        return find_nodegroup(request)
    else:
        return NodeGroup.objects.get(uuid=uuid)


def pxeconfig(request):
    """Get the PXE configuration given a node's details.

    Returns a JSON object corresponding to a
    :class:`provisioningserver.kernel_opts.KernelParameters` instance.

    This is now fairly decoupled from pxelinux's TFTP filename encoding
    mechanism, with one notable exception. Call this function with (mac, arch,
    subarch) and it will do the right thing. If details it needs are missing
    (ie. arch/subarch missing when the MAC is supplied but unknown), then it
    will as an exception return an HTTP NO_CONTENT (204) in the expectation
    that this will be translated to a TFTP file not found and pxelinux (or an
    emulator) will fall back to default-<arch>-<subarch> (in the case of an
    alternate architecture emulator) or just straight to default (in the case
    of native pxelinux on i386 or amd64). See bug 1041092 for details and
    discussion.

    :param mac: MAC address to produce a boot configuration for.
    :param arch: Architecture name (in the pxelinux namespace, eg. 'arm' not
        'armhf').
    :param subarch: Subarchitecture name (in the pxelinux namespace).
    :param local: The IP address of the cluster controller.
    :param remote: The IP address of the booting node.
    :param cluster_uuid: UUID of the cluster responsible for this node.
        If omitted, the call will attempt to figure it out based on the
        requesting IP address, for compatibility.  Passing `cluster_uuid`
        is preferred.
    """
    node = get_node_from_mac_string(request.GET.get('mac', None))

    if node is None or node.status == NODE_STATUS.COMMISSIONING:
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')
    else:
        osystem = node.get_osystem()
        series = node.get_distro_series()

    if node:
        arch, subarch = node.architecture.split('/')
        preseed_url = compose_preseed_url(node)
        # The node's hostname may include a domain, but we ignore that
        # and use the one from the nodegroup instead.
        hostname = strip_domain(node.hostname)
        nodegroup = node.nodegroup
        domain = nodegroup.name
    else:
        nodegroup = find_nodegroup_for_pxeconfig_request(request)
        preseed_url = compose_enlistment_preseed_url(nodegroup=nodegroup)
        hostname = 'maas-enlist'
        domain = Config.objects.get_config('enlistment_domain')

        arch = get_optional_param(request.GET, 'arch')
        if arch is None:
            if 'mac' in request.GET:
                # Request was pxelinux.cfg/01-<mac>, so attempt fall back
                # to pxelinux.cfg/default-<arch>-<subarch> for arch detection.
                return HttpResponse(status=httplib.NO_CONTENT)
            else:
                # Look in BootImage for an image that actually exists for the
                # current series. If nothing is found, fall back to i386 like
                # we used to. LP #1181334
                image = BootImage.objects.get_default_arch_image_in_nodegroup(
                    nodegroup, osystem, series, purpose='commissioning')
                if image is None:
                    arch = 'i386'
                else:
                    arch = image.architecture

        subarch = get_optional_param(request.GET, 'subarch', 'generic')

    # Get the purpose, without a selected label
    purpose = get_boot_purpose(
        node, osystem, arch, subarch, series, label=None)

    # If we are booting with "xinstall", then we should always return the
    # commissioning operating system and distro_series.
    if purpose == "xinstall":
        osystem = Config.objects.get_config('commissioning_osystem')
        series = Config.objects.get_config('commissioning_distro_series')

    # We use as our default label the label of the most recent image for
    # the criteria we've assembled above. If there is no latest image
    # (which should never happen in reality but may happen in tests), we
    # fall back to using 'no-such-image' as our default.
    latest_image = BootImage.objects.get_latest_image(
        nodegroup, osystem, arch, subarch, series, purpose)
    if latest_image is None:
        # XXX 2014-03-18 gmb bug=1294131:
        #     We really ought to raise an exception here so that client
        #     and server can handle it according to their needs. At the
        #     moment, though, that breaks too many tests in awkward
        #     ways.
        latest_label = 'no-such-image'
    else:
        latest_label = latest_image.label
        # subarch may be different from the request because newer images
        # support older hardware enablement, e.g. trusty/generic
        # supports trusty/hwe-s. We must override the subarch to the one
        # on the image otherwise the config path will be wrong if
        # get_latest_image() returned an image with a different subarch.
        subarch = latest_image.subarchitecture
    label = get_optional_param(request.GET, 'label', latest_label)

    # Get the supported purpose with the boot label
    purpose = get_boot_purpose(node, osystem, arch, subarch, series, label)

    if node is not None:
        # We don't care if the kernel opts is from the global setting or a tag,
        # just get the options
        _, effective_kernel_opts = node.get_effective_kernel_options()

        # Add any extra options from a third party driver.
        use_driver = Config.objects.get_config('enable_third_party_drivers')
        if use_driver:
            driver = get_third_party_driver(node)
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
        # If there's no node defined then we must be enlisting here, but
        # we still need to return the global kernel options.
        extra_kernel_opts = Config.objects.get_config("kernel_opts")

    server_address = get_maas_facing_server_address(nodegroup=nodegroup)
    cluster_address = get_mandatory_param(request.GET, "local")

    params = KernelParameters(
        osystem=osystem, arch=arch, subarch=subarch, release=series,
        label=label, purpose=purpose, hostname=hostname, domain=domain,
        preseed_url=preseed_url, log_host=server_address,
        fs_host=cluster_address, extra_opts=extra_kernel_opts)

    return HttpResponse(
        json.dumps(params._asdict()),
        content_type="application/json")


def warn_if_missing_boot_images():
    """Show a UI warning if any nodegroups have no boot images.

    This is a coarse approximation for "have boot images been imported yet?"
    The warning appears if any nodegroup is still completely without boot
    images, as is the case when the system starts up initially.
    """
    nodegroup_ids_with_images = BootImage.objects.values_list(
        "nodegroup_id", flat=True)
    nodegroups_without_images = NodeGroup.objects.exclude(
        id__in=nodegroup_ids_with_images)
    nodegroups_without_images = nodegroups_without_images.filter(
        status=NODEGROUP_STATUS.ACCEPTED)
    if nodegroups_without_images.exists():
        accepted_clusters_url = absolute_reverse("cluster-list")
        warning = dedent("""\
            Some cluster controllers are missing boot images.  Either the
            import task has not been initiated (for each cluster, the task
            must be <a href=%s>initiated by hand</a> the first time), or
            the import task failed.
            """ % quoteattr(accepted_clusters_url))
        register_persistent_error(COMPONENT.IMPORT_PXE_FILES, warning)
    else:
        discard_persistent_error(COMPONENT.IMPORT_PXE_FILES)


def summarise_boot_image_object(image_object):
    """Return a tuple representing identifying properties of a `BootImage`.

    This function has a counterpart, `summarise_boot_image_dict`.  The two
    return the same value for the same boot image.

    :return: A tuple of the image's osystem, architecture, subarchitecture,
        release, label, and purpose.
    """
    return (
        image_object.osystem,
        image_object.architecture,
        image_object.subarchitecture,
        image_object.release,
        image_object.label,
        image_object.purpose,
        image_object.supported_subarches,
        )


def summarise_boot_image_dict(image_dict):
    """Return a tuple representing a reported boot-image dict.

    This is the counterpart to `summarise_boot_image_object`.  The two return
    the same value for the same boot image.

    :return: A tuple of the image's osystem, architecture, subarchitecture,
        release, label, and purpose.
    """
    return (
        image_dict['osystem'],
        image_dict['architecture'],
        image_dict.get('subarchitecture', 'generic'),
        image_dict['release'],
        image_dict.get('label', 'release'),
        image_dict['purpose'],
        image_dict.get('supported_subarches', ''),
        )


def summarise_reported_images(request):
    """Return boot images reported by `request`.

    :param request: An http request as received by `report_boot_images`.
    :return: A set of tuples as produced by `summarise_boot_image_dict`.
    """
    return {
        summarise_boot_image_dict(image)
        for image in json.loads(get_mandatory_param(request.data, 'images'))
        }


def summarise_stored_images(nodegroup):
    """Return boot images for `nodegroup` as found in the database.

    :param nodegroup: The nodegroup whose boot images should be queried.
    :return: A set of tuples as produced by `summarise_boot_image_object`.
    """
    return {
        summarise_boot_image_object(image)
        for image in BootImage.objects.filter(nodegroup=nodegroup)
        }


def store_boot_images(nodegroup, reported_images, stored_images):
    """Store newly reported boot images in the database.

    :param nodegroup: The `NodeGroup` whose boot images are being reported.
    :param reported_images: Images being reported, as generated by
        `summarise_reported_images`.
    :param stored_images: Images already in the database, as generated by
        `summarise_stored_images`.
    """
    new_images = reported_images - stored_images
    for (osystem, arch, subarch, release, label, purpose,
            supported_subarches) in new_images:
        BootImage.objects.register_image(
            nodegroup=nodegroup, osystem=osystem, architecture=arch,
            subarchitecture=subarch, release=release, purpose=purpose,
            label=label, supported_subarches=supported_subarches)


def prune_boot_images(nodegroup, reported_images, stored_images):
    """Remove boot images for `nodegroup` which are no longer reported.

    When a nodegroup reports its boot imgaes, it reports all the images it
    has.  Therefore, any image not being reported is obsolete.  This function
    removes such images from the database.

    :param nodegroup: The `NodeGroup` whose boot images are being reported.
    :param reported_images: Images being reported, as generated by
        `summarise_reported_images`.
    :param stored_images: Images already in the database, as generated by
        `summarise_stored_images`.
    """
    # supported_subarches is not a key field, so images can still match
    # even when it differs.
    reported = set(
        (osystem, arch, subarch, release, label, purpose)
        for (osystem, arch, subarch, release, label, purpose, _)
        in reported_images)
    stored = set(
        (osystem, arch, subarch, release, label, purpose)
        for (osystem, arch, subarch, release, label, purpose, _)
        in stored_images)

    removed_images = stored - reported
    for osystem, arch, subarch, release, label, purpose in removed_images:
        db_images = BootImage.objects.filter(
            osystem=osystem, architecture=arch, subarchitecture=subarch,
            release=release, label=label, purpose=purpose)
        db_images.delete()


DISPLAYED_BOOTIMAGE_FIELDS = (
    'id',
    'osystem',
    'release',
    'architecture',
    'subarchitecture',
    'purpose',
    'label',
)


class BootImageHandler(OperationsHandler):
    """Manage a boot image."""
    api_doc_section_name = "Boot image"
    create = replace = update = delete = None

    model = BootImage
    fields = DISPLAYED_BOOTIMAGE_FIELDS

    def read(self, request, uuid, id):
        """Read a boot image."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        return get_object_or_404(
            BootImage, nodegroup=nodegroup, id=id)

    @classmethod
    def resource_uri(cls, bootimage=None):
        if bootimage is None:
            id = 'id'
            uuid = 'uuid'
        else:
            id = bootimage.id
            uuid = bootimage.nodegroup.uuid
        return ('boot_image_handler', (uuid, id))


class BootImagesHandler(OperationsHandler):
    """Manage the collection of boot images."""
    api_doc_section_name = "Boot images"

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls, nodegroup=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        return ('boot_images_handler', [uuid])

    def read(self, request, uuid):
        """List boot images.

        Get a listing of a cluster's boot images.

        :param uuid: The UUID of the cluster for which the images
            should be listed.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        return BootImage.objects.filter(nodegroup=nodegroup)

    @operation(idempotent=False)
    def report_boot_images(self, request, uuid):
        """Report images available to net-boot nodes from.

        :param uuid: The UUID of the cluster for which the images are
            being reported.
        :param images: A list of dicts, each describing a boot image with
            these properties: `os`, `architecture`, `subarchitecture`,
            `release`, `purpose`, and optionally, `label` (which defaults
            to "release"). These should match the code that determines TFTP
            paths for these images.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        check_nodegroup_access(request, nodegroup)
        reported_images = summarise_reported_images(request)
        existing_images = summarise_stored_images(nodegroup)
        store_boot_images(nodegroup, reported_images, existing_images)
        prune_boot_images(nodegroup, reported_images, existing_images)
        warn_if_missing_boot_images()
        return HttpResponse("OK")


DISPLAYED_BOOTSOURCE_FIELDS = (
    'id',
    'url',
    'keyring_filename',
    'keyring_data',
)


def json_boot_source(boot_source, request):
    """Convert boot_source into a json object.

    Use the same fields used when serialising objects, but base64-encode
    keyring_data.
    """
    dict_representation = {
        fieldname: getattr(boot_source, fieldname)
        for fieldname in DISPLAYED_BOOTSOURCE_FIELDS
        }
    # Encode the keyring_data as base64.
    keyring_data = getattr(boot_source, 'keyring_data')
    dict_representation['keyring_data'] = b64encode(keyring_data)
    dict_representation['resource_uri'] = reverse(
        'boot_source_handler',
        args=[boot_source.cluster.uuid, boot_source.id])
    emitter = JSONEmitter(dict_representation, typemapper, None)
    stream = emitter.render(request)
    return stream


class BootSourceHandler(OperationsHandler):
    """Manage a boot source."""
    api_doc_section_name = "Boot source"
    create = replace = None

    model = BootSource
    fields = DISPLAYED_BOOTSOURCE_FIELDS

    def read(self, request, uuid, id):
        """Read a boot source."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        boot_source = get_object_or_404(
            BootSource, cluster=nodegroup, id=id)
        stream = json_boot_source(boot_source, request)
        return HttpResponse(
            stream, mimetype='application/json; charset=utf-8',
            status=httplib.OK)

    def update(self, request, uuid, id):
        """Update a specific boot source.

        :param url: The URL of the BootSource.
        :param keyring_filename: The path to the keyring file for this
            BootSource.
        :param keyring_filename: The GPG keyring for this BootSource,
            base64-encoded data.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        boot_source = get_object_or_404(
            BootSource, cluster=nodegroup, id=id)
        form = BootSourceForm(
            data=request.data, files=request.FILES, instance=boot_source)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    def delete(self, request, uuid, id):
        """Delete a specific boot source."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        boot_source = get_object_or_404(
            BootSource, cluster=nodegroup, id=id)
        boot_source.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, bootsource=None):
        if bootsource is None:
            id = 'id'
            uuid = 'uuid'
        else:
            id = bootsource.id
            uuid = bootsource.cluster.uuid
        return ('boot_source_handler', (uuid, id))


class BootSourcesHandler(OperationsHandler):
    """Manage the collection of boot sources."""
    api_doc_section_name = "Boot sources"

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls, nodegroup=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        return ('boot_sources_handler', [uuid])

    def read(self, request, uuid):
        """List boot sources.

        Get a listing of a cluster's boot sources.

        :param uuid: The UUID of the cluster for which the images
            should be listed.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        return BootSource.objects.filter(cluster=nodegroup)

    def create(self, request, uuid):
        """Create a new boot source.

        :param url: The URL of the BootSource.
        :param keyring_filename: The path to the keyring file for
            this BootSource.
        :param keyring_data: The GPG keyring for this BootSource,
            base64-encoded.
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        form = BootSourceForm(
            data=request.data, files=request.FILES,
            nodegroup=nodegroup)
        if form.is_valid():
            boot_source = form.save()
            stream = json_boot_source(boot_source, request)
            return HttpResponse(
                stream, mimetype='application/json; charset=utf-8',
                status=httplib.CREATED)
        else:
            raise ValidationError(form.errors)


DISPLAYED_BOOTSOURCESELECTION_FIELDS = (
    'id',
    'release',
    'arches',
    'subarches',
    'labels',
)


class BootSourceSelectionHandler(OperationsHandler):
    """Manage a boot source selection."""
    api_doc_section_name = "Boot source selection"
    create = replace = None

    model = BootSourceSelection
    fields = DISPLAYED_BOOTSOURCESELECTION_FIELDS

    def read(self, request, uuid, boot_source_id, id):
        """Read a boot source selection."""
        boot_source = get_object_or_404(
            BootSource, cluster__uuid=uuid, id=boot_source_id)
        return get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id)

    def update(self, request, uuid, boot_source_id, id):
        """Update a specific boot source selection.

        :param release: The Ubuntu release for which to import resources.
        :param arches: The list of architectures for which to import resources.
        :param subarches: The list of subarchitectures for which to import
            resources.
        :param labels: The list of labels for which to import resources.
        """
        boot_source = get_object_or_404(
            BootSource, cluster__uuid=uuid, id=boot_source_id)
        boot_source_selection = get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id)
        form = BootSourceSelectionForm(
            data=request.data, instance=boot_source_selection)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    def delete(self, request, uuid, boot_source_id, id):
        """Delete a specific boot source."""
        boot_source = get_object_or_404(
            BootSource, cluster__uuid=uuid, id=boot_source_id)
        boot_source_selection = get_object_or_404(
            BootSourceSelection, boot_source=boot_source, id=id)
        boot_source_selection.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, bootsourceselection=None):
        if bootsourceselection is None:
            id = 'id'
            uuid = 'uuid'
            boot_source_id = 'boot_source_id'
        else:
            id = bootsourceselection.id
            boot_source = bootsourceselection.boot_source
            uuid = boot_source.cluster.uuid
            boot_source_id = boot_source.id
        return ('boot_source_selection_handler', (uuid, boot_source_id, id))


class BootSourceSelectionsHandler(OperationsHandler):
    """Manage the collection of boot source selections."""
    api_doc_section_name = "Boot source selections"

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls, nodegroup=None, boot_source=None):
        if nodegroup is None:
            uuid = 'uuid'
        else:
            uuid = nodegroup.uuid
        if boot_source is None:
            boot_source_id = 'boot_source_id'
        else:
            boot_source_id = boot_source.id
        return ('boot_source_selections_handler', [uuid, boot_source_id])

    def read(self, request, uuid, boot_source_id):
        """List boot source selections.

        Get a listing of a boot source's selections.
        """
        boot_source = get_object_or_404(
            BootSource, cluster__uuid=uuid, id=boot_source_id)
        return BootSourceSelection.objects.filter(boot_source=boot_source)

    def create(self, request, uuid, boot_source_id):
        """Create a new boot source selection.

        :param release: The Ubuntu release for which to import resources.
        :param arches: The architecture list for which to import resources.
        :param subarches: The subarchitecture list for which to import
            resources.
        :param labels: The label lists for which to import resources.
        """
        boot_source = get_object_or_404(
            BootSource, cluster__uuid=uuid, id=boot_source_id)
        form = BootSourceSelectionForm(
            data=request.data, boot_source=boot_source)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)


def get_content_parameter(request):
    """Get the "content" parameter from a CommissioningScript POST or PUT."""
    content_file = get_mandatory_param(request.FILES, 'content')
    return content_file.read()


class CommissioningScriptsHandler(OperationsHandler):
    """Manage custom commissioning scripts.

    This functionality is only available to administrators.
    """
    api_doc_section_name = "Commissioning scripts"

    update = delete = None

    def read(self, request):
        """List commissioning scripts."""
        return [
            script.name
            for script in CommissioningScript.objects.all().order_by('name')]

    def create(self, request):
        """Create a new commissioning script.

        Each commissioning script is identified by a unique name.

        By convention the name should consist of a two-digit number, a dash,
        and a brief descriptive identifier consisting only of ASCII
        characters.  You don't need to follow this convention, but not doing
        so opens you up to risks w.r.t. encoding and ordering.  The name must
        not contain any whitespace, quotes, or apostrophes.

        A commissioning node will run each of the scripts in lexicographical
        order.  There are no promises about how non-ASCII characters are
        sorted, or even how upper-case letters are sorted relative to
        lower-case letters.  So where ordering matters, use unique numbers.

        Scripts built into MAAS will have names starting with "00-maas" or
        "99-maas" to ensure that they run first or last, respectively.

        Usually a commissioning script will be just that, a script.  Ideally a
        script should be ASCII text to avoid any confusion over encoding.  But
        in some cases a commissioning script might consist of a binary tool
        provided by a hardware vendor.  Either way, the script gets passed to
        the commissioning node in the exact form in which it was uploaded.

        :param name: Unique identifying name for the script.  Names should
            follow the pattern of "25-burn-in-hard-disk" (all ASCII, and with
            numbers greater than zero, and generally no "weird" characters).
        :param content: A script file, to be uploaded in binary form.  Note:
            this is not a normal parameter, but a file upload.  Its filename
            is ignored; MAAS will know it by the name you pass to the request.
        """
        name = get_mandatory_param(request.data, 'name')
        content = Bin(get_content_parameter(request))
        return CommissioningScript.objects.create(name=name, content=content)

    @classmethod
    def resource_uri(cls):
        return ('commissioning_scripts_handler', [])


class CommissioningScriptHandler(OperationsHandler):
    """Manage a custom commissioning script.

    This functionality is only available to administrators.
    """
    api_doc_section_name = "Commissioning script"

    model = CommissioningScript
    fields = ('name', 'content')

    # Relies on Piston's built-in DELETE implementation.  There is no POST.
    create = None

    def read(self, request, name):
        """Read a commissioning script."""
        script = get_object_or_404(CommissioningScript, name=name)
        return HttpResponse(script.content, content_type='application/binary')

    def delete(self, request, name):
        """Delete a commissioning script."""
        script = get_object_or_404(CommissioningScript, name=name)
        script.delete()
        return rc.DELETED

    def update(self, request, name):
        """Update a commissioning script."""
        content = Bin(get_content_parameter(request))
        script = get_object_or_404(CommissioningScript, name=name)
        script.content = content
        script.save()

    @classmethod
    def resource_uri(cls, script=None):
        # See the comment in NodeHandler.resource_uri
        script_name = 'name'
        if script is not None:
            script_name = script.name
        return ('commissioning_script_handler', (script_name, ))


class CommissioningResultsHandler(OperationsHandler):
    """Read the collection of NodeCommissionResult in the MAAS."""
    api_doc_section_name = "Commissioning results"
    create = read = update = delete = None

    model = NodeCommissionResult
    fields = ('name', 'script_result', 'updated', 'created', 'node', 'data')

    @operation(idempotent=True)
    def list(self, request):
        """List NodeCommissionResult visible to the user, optionally filtered.

        :param system_id: An optional list of system ids.  Only the
            commissioning results related to the nodes with these system ids
            will be returned.
        :type system_id: iterable
        :param name: An optional list of names.  Only the commissioning
            results with the specified names will be returned.
        :type name: iterable
        """
        # Get filters from request.
        system_ids = get_optional_list(request.GET, 'system_id')
        names = get_optional_list(request.GET, 'name')
        nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=system_ids)
        results = NodeCommissionResult.objects.filter(node_id__in=nodes)
        if names is not None:
            results = results.filter(name__in=names)
        return results

    @classmethod
    def resource_uri(cls, result=None):
        return ('commissioning_results_handler', [])


def describe(request):
    """Return a description of the whole MAAS API.

    :param request: The http request for this document.  This is used to
        derive the URL where the client expects to see the MAAS API.
    :return: A JSON object describing the whole MAAS API.  Links to the API
        will use the same scheme and hostname that the client used in
        `request`.
    """
    from maasserver import urls_api as urlconf
    resources = [
        describe_resource(resource)
        for resource in find_api_resources(urlconf)
        ]
    # Make all URIs absolute. Clients - and the command-line client in
    # particular - expect that all handler URIs are absolute, not just paths.
    # The handler URIs returned by describe_resource() are relative paths.
    absolute = partial(build_absolute_uri, request)
    for resource in resources:
        for handler_type in "anon", "auth":
            handler = resource[handler_type]
            if handler is not None:
                handler["uri"] = absolute(handler["path"])
    # Package it all up.
    description = {
        "doc": "MAAS API",
        "resources": resources,
        }
    # For backward compatibility, add "handlers" as an alias for all not-None
    # anon and auth handlers in "resources".
    description["handlers"] = []
    description["handlers"].extend(
        resource["anon"] for resource in description["resources"]
        if resource["anon"] is not None)
    description["handlers"].extend(
        resource["auth"] for resource in description["resources"]
        if resource["auth"] is not None)
    return HttpResponse(
        json.dumps(description),
        content_type="application/json")


class ZoneHandler(OperationsHandler):
    """Manage a physical zone.

    Any node is in a physical zone, or "zone" for short.  The meaning of a
    physical zone is up to you: it could identify e.g. a server rack, a
    network, or a data centre.  Users can then allocate nodes from specific
    physical zones, to suit their redundancy or performance requirements.

    This functionality is only available to administrators.  Other users can
    view physical zones, but not modify them.
    """
    api_doc_section_name = "Zone"
    model = Zone
    fields = ('name', 'description')

    # Creation happens on the ZonesHandler.
    create = None

    def read(self, request, name):
        """GET request.  Return zone."""
        return get_object_or_404(Zone, name=name)

    @admin_method
    def update(self, request, name):
        """PUT request.  Update zone."""
        zone = get_object_or_404(Zone, name=name)
        form = ZoneForm(instance=zone, data=request.data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        return form.save()

    @admin_method
    def delete(self, request, name):
        """DELETE request.  Delete zone."""
        zone = get_one(Zone.objects.filter(name=name))
        if zone is not None:
            zone.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, zone=None):
        # See the comment in NodeHandler.resource_uri.
        if zone is None:
            name = 'name'
        else:
            name = zone.name
        return ('zone_handler', (name, ))


class ZonesHandler(OperationsHandler):
    """Manage physical zones."""
    api_doc_section_name = "Zones"
    update = delete = None

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('zones_handler', [])

    @admin_method
    def create(self, request):
        """Create a new physical zone.

        :param name: Identifier-style name for the new zone.
        :type name: unicode
        :param description: Free-form description of the new zone.
        :type description: unicode
        """
        form = ZoneForm(request.data)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    def read(self, request):
        """List zones.

        Get a listing of all the physical zones.
        """
        return Zone.objects.all().order_by('name')


class NetworkHandler(OperationsHandler):
    """Manage a network."""
    api_doc_section_name = "Network"

    model = Network
    fields = ('name', 'ip', 'netmask', 'vlan_tag', 'description')

    # Creation happens on the NetworksHandler.
    create = None

    def read(self, request, name):
        """Read network definition."""
        return get_object_or_404(Network, name=name)

    @admin_method
    def update(self, request, name):
        """Update network definition.

        :param name: A simple name for the network, to make it easier to
            refer to.  Must consist only of letters, digits, dashes, and
            underscores.
        :param ip: Base IP address for the network, e.g. `10.1.0.0`.  The host
            bits will be zeroed.
        :param netmask: Subnet mask to indicate which parts of an IP address
            are part of the network address.  For example, `255.255.255.0`.
        :param vlan_tag: Optional VLAN tag: a number between 1 and 0xffe (4094)
            inclusive, or zero for an untagged network.
        :param description: Detailed description of the network for the benefit
            of users and administrators.
        """
        network = get_object_or_404(Network, name=name)
        form = NetworkForm(instance=network, data=request.data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        return form.save()

    @admin_method
    def delete(self, request, name):
        """Delete network definition.

        A network cannot be deleted while it still has nodes attached to it.
        """
        network = get_one(Network.objects.filter(name=name))
        if network is not None:
            network.delete()
        return rc.DELETED

    @admin_method
    @operation(idempotent=False)
    def connect_macs(self, request, name):
        """Connect the given MAC addresses to this network.

        These MAC addresses must belong to nodes in the MAAS, and have been
        registered as such in MAAS.

        Connecting a network interface to a network which it is already
        connected to does nothing.

        :param macs: A list of node MAC addresses, in text form.
        """
        network = get_object_or_404(Network, name=name)
        form = NetworkConnectMACsForm(network=network, data=request.data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        form.save()

    @admin_method
    @operation(idempotent=False)
    def disconnect_macs(self, request, name):
        """Disconnect the given MAC addresses from this network.

        Removing a MAC address from a network which it is not connected to
        does nothing.

        :param macs: A list of node MAC addresses, in text form.
        """
        network = get_object_or_404(Network, name=name)
        form = NetworkDisconnectMACsForm(network=network, data=request.data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        form.save()

    @operation(idempotent=True)
    def list_connected_macs(self, request, name):
        """Returns the list of MAC addresses connected to this network.

        Only MAC addresses for nodes visible to the requesting user are
        returned.
        """
        network = get_object_or_404(Network, name=name)
        visible_nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW,
            from_nodes=Node.objects.all())
        return network.macaddress_set.filter(node__in=visible_nodes).order_by(
            'node__hostname', 'mac_address')

    @classmethod
    def resource_uri(cls, network=None):
        # See the comment in NodeHandler.resource_uri.
        if network is None:
            name = 'name'
        else:
            name = network.name
        return ('network_handler', (name, ))


class NetworksHandler(OperationsHandler):
    """Manage the networks."""
    api_doc_section_name = "Networks"

    update = delete = None

    def read(self, request):
        """List networks.

        :param node: Optionally, nodes which must be attached to any returned
            networks.  If more than one node is given, the result will be
            restricted to networks that these nodes have in common.
        """
        form = NetworksListingForm(data=request.GET)
        if not form.is_valid():
            raise ValidationError(form.errors)
        return form.filter_networks(Network.objects.all())

    @admin_method
    def create(self, request):
        """Define a network.

        :param name: A simple name for the network, to make it easier to
            refer to.  Must consist only of letters, digits, dashes, and
            underscores.
        :param ip: Base IP address for the network, e.g. `10.1.0.0`.  The host
            bits will be zeroed.
        :param netmask: Subnet mask to indicate which parts of an IP address
            are part of the network address.  For example, `255.255.255.0`.
        :param vlan_tag: Optional VLAN tag: a number between 1 and 0xffe (4094)
            inclusive, or zero for an untagged network.
        :param description: Detailed description of the network for the benefit
            of users and administrators.
        """
        form = NetworkForm(request.data)
        if not form.is_valid():
            raise ValidationError(form.errors)
        return form.save()

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('networks_handler', [])
