# Copyright 2012 Canonical Ltd.  This software is licensed under the
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

__metaclass__ = type
__all__ = [
    "AccountHandler",
    "AnonNodeGroupsHandler",
    "AnonNodesHandler",
    "AnonymousOperationsHandler",
    "api_doc",
    "api_doc_title",
    "BootImagesHandler",
    "FilesHandler",
    "get_oauth_token",
    "NodeGroupsHandler",
    "NodeGroupInterfaceHandler",
    "NodeGroupInterfacesHandler",
    "NodeHandler",
    "NodeMacHandler",
    "NodeMacsHandler",
    "NodesHandler",
    "OperationsHandler",
    "TagHandler",
    "TagsHandler",
    "pxeconfig",
    "render_api_docs",
    "store_node_power_parameters",
    ]

from base64 import b64decode
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

from celery.app import app_or_default
from django.conf import settings
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.db.utils import DatabaseError
from django.forms.models import model_to_dict
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    QueryDict,
    )
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from docutils import core
from formencode import validators
from formencode.validators import Invalid
from maasserver.apidoc import (
    describe_resource,
    find_api_resources,
    generate_api_docs,
    )
from maasserver.components import (
    discard_persistent_error,
    register_persistent_error,
    )
from maasserver.enum import (
    ARCHITECTURE,
    COMPONENT,
    NODE_PERMISSION,
    NODE_STATUS,
    NODEGROUP_STATUS,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodesNotAvailable,
    NodeStateViolation,
    Unauthorized,
    )
from maasserver.fields import (
    mac_re,
    validate_mac,
    )
from maasserver.forms import (
    get_node_create_form,
    get_node_edit_form,
    NodeGroupInterfaceForm,
    NodeGroupWithInterfacesForm,
    TagForm,
    )
from maasserver.models import (
    BootImage,
    Config,
    DHCPLease,
    FileStorage,
    MACAddress,
    Node,
    NodeGroup,
    NodeGroupInterface,
    Tag,
    )
from maasserver.models.node import CONSTRAINTS_MAAS_MAP
from maasserver.preseed import (
    compose_enlistment_preseed_url,
    compose_preseed_url,
    )
from maasserver.server_address import get_maas_facing_server_address
from maasserver.utils import (
    absolute_reverse,
    build_absolute_uri,
    map_enum,
    strip_domain,
    )
from maasserver.utils.orm import get_one
from piston.handler import (
    AnonymousBaseHandler,
    BaseHandler,
    HandlerMetaClass,
    )
from piston.models import Token
from piston.resource import Resource
from piston.utils import rc
from provisioningserver.enum import POWER_TYPE
from provisioningserver.kernel_opts import KernelParameters
import simplejson as json


class OperationsResource(Resource):
    """A resource supporting operation dispatch.

    All requests are passed onto the handler's `dispatch` method. See
    :class:`OperationsHandler`.
    """

    crudmap = Resource.callmap
    callmap = dict.fromkeys(crudmap, "dispatch")


class RestrictedResource(OperationsResource):

    def authenticate(self, request, rm):
        actor, anonymous = super(
            RestrictedResource, self).authenticate(request, rm)
        if not anonymous and not request.user.is_active:
            raise PermissionDenied("User is not allowed access to this API.")
        else:
            return actor, anonymous


class AdminRestrictedResource(RestrictedResource):

    def authenticate(self, request, rm):
        actor, anonymous = super(
            AdminRestrictedResource, self).authenticate(request, rm)
        if anonymous or not request.user.is_superuser:
            raise PermissionDenied("User is not allowed access to this API.")
        else:
            return actor, anonymous


def operation(idempotent, exported_as=None):
    """Decorator to make a method available on the API.

    :param idempotent: If this operation is idempotent. Idempotent operations
        are made available via HTTP GET, non-idempotent operations via HTTP
        POST.
    :param exported_as: Optional operation name; defaults to the name of the
        exported method.
    """
    method = "GET" if idempotent else "POST"

    def _decorator(func):
        if exported_as is None:
            func.export = method, func.__name__
        else:
            func.export = method, exported_as
        return func

    return _decorator


class OperationsHandlerType(HandlerMetaClass):
    """Type for handlers that dispatch operations.

    Collects all the exported operations, CRUD and custom, into the class's
    `exports` attribute. This is a signature:function mapping, where signature
    is an (http-method, operation-name) tuple. If operation-name is None, it's
    a CRUD method.

    The `allowed_methods` attribute is calculated as the union of all HTTP
    methods required for the exported CRUD and custom operations.
    """

    def __new__(metaclass, name, bases, namespace):
        cls = super(OperationsHandlerType, metaclass).__new__(
            metaclass, name, bases, namespace)

        # Create a signature:function mapping for CRUD operations.
        crud = {
            (http_method, None): getattr(cls, method)
            for http_method, method in OperationsResource.crudmap.items()
            if getattr(cls, method, None) is not None
            }

        # Create a signature:function mapping for non-CRUD operations.
        operations = {
            attribute.export: attribute
            for attribute in vars(cls).values()
            if getattr(attribute, "export", None) is not None
            }

        # Create the exports mapping.
        exports = {}
        exports.update(crud)
        exports.update(operations)

        # Update the class.
        cls.exports = exports
        cls.allowed_methods = frozenset(
            http_method for http_method, name in exports)

        return cls


class OperationsHandlerMixin:
    """Handler mixin for operations dispatch.

    This enabled dispatch to custom functions that piggyback on HTTP methods
    that ordinarily, in Piston, are used for CRUD operations.

    This must be used in cooperation with :class:`OperationsResource` and
    :class:`OperationsHandlerType`.
    """

    def dispatch(self, request, *args, **kwargs):
        signature = request.method.upper(), request.REQUEST.get("op")
        function = self.exports.get(signature)
        if function is None:
            return HttpResponseBadRequest(
                "Unrecognised signature: %s %s" % signature)
        else:
            return function(self, request, *args, **kwargs)


class OperationsHandler(
    OperationsHandlerMixin, BaseHandler):
    """Base handler that supports operation dispatch."""

    __metaclass__ = OperationsHandlerType


class AnonymousOperationsHandler(
    OperationsHandlerMixin, AnonymousBaseHandler):
    """Anonymous base handler that supports operation dispatch."""

    __metaclass__ = OperationsHandlerType


def get_mandatory_param(data, key, validator=None):
    """Get the parameter from the provided data dict or raise a ValidationError
    if this parameter is not present.

    :param data: The data dict (usually request.data or request.GET where
        request is a django.http.HttpRequest).
    :param data: dict
    :param key: The parameter's key.
    :type key: basestring
    :param validator: An optional validator that will be used to validate the
         retrieved value.
    :type validator: formencode.validators.Validator
    :return: The value of the parameter.
    :raises: ValidationError
    """
    value = data.get(key, None)
    if value is None:
        raise ValidationError("No provided %s!" % key)
    if validator is not None:
        try:
            return validator.to_python(value)
        except Invalid, e:
            raise ValidationError("Invalid %s: %s" % (key, e.msg))
    else:
        return value


def get_optional_list(data, key, default=None):
    """Get the list from the provided data dict or return a default value.
    """
    value = data.getlist(key)
    if value == []:
        return default
    else:
        return value


def get_list_from_dict_or_multidict(data, key, default=None):
    """Get a list from 'data'.

    If data is a MultiDict, then we use 'getlist' if the data is a plain dict,
    then we just use __getitem__.

    The rationale is that data POSTed as multipart/form-data gets parsed into a
    MultiDict, but data POSTed as application/json gets parsed into a plain
    dict(key:list).
    """
    getlist = getattr(data, 'getlist', None)
    if getlist is not None:
        return getlist(key, default)
    return data.get(key, default)


def extract_oauth_key_from_auth_header(auth_data):
    """Extract the oauth key from auth data in HTTP header.

    :param auth_data: {string} The HTTP Authorization header.

    :return: The oauth key from the header, or None.
    """
    for entry in auth_data.split():
        key_value = entry.split('=', 1)
        if len(key_value) == 2:
            key, value = key_value
            if key == 'oauth_token':
                return value.rstrip(',').strip('"')
    return None


def extract_oauth_key(request):
    """Extract the oauth key from a request's headers.

    Raises :class:`Unauthorized` if no key is found.
    """
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header is None:
        raise Unauthorized("No authorization header received.")
    key = extract_oauth_key_from_auth_header(auth_header)
    if key is None:
        raise Unauthorized("Did not find request's oauth token.")
    return key


def get_oauth_token(request):
    """Get the OAuth :class:`piston.models.Token` used for `request`.

    Raises :class:`Unauthorized` if no key is found, or if the token is
    unknown.
    """
    try:
        return Token.objects.get(key=extract_oauth_key(request))
    except Token.DoesNotExist:
        raise Unauthorized("Unknown OAuth token.")


def get_overrided_query_dict(defaults, data):
    """Returns a QueryDict with the values of 'defaults' overridden by the
    values in 'data'.

    :param defaults: The dictionary containing the default values.
    :type defaults: dict
    :param data: The data used to override the defaults.
    :type data: :class:`django.http.QueryDict`
    :return: The updated QueryDict.
    :raises: :class:`django.http.QueryDict`
    """
    # Create a writable query dict.
    new_data = QueryDict('').copy()
    # Missing fields will be taken from the node's current values.  This
    # is to circumvent Django's ModelForm (form created from a model)
    # default behaviour that requires all the fields to be defined.
    new_data.update(defaults)
    # We can't use update here because data is a QueryDict and 'update'
    # does not replaces the old values with the new as one would expect.
    for k, v in data.items():
        new_data[k] = v
    return new_data


# Node's fields exposed on the API.
DISPLAYED_NODE_FIELDS = (
    'system_id',
    'hostname',
    ('macaddress_set', ('mac_address',)),
    'architecture',
    'status',
    'netboot',
    'power_type',
    'tag_names',
    )


def store_node_power_parameters(node, request):
    """Store power parameters in request.

    The parameters should be JSON, passed with key `power_parameters`.
    """
    power_type = request.POST.get("power_type", None)
    if power_type is None:
        return

    power_types = map_enum(POWER_TYPE).values()
    if power_type in power_types:
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
    create = None  # Disable create.
    model = Node
    fields = DISPLAYED_NODE_FIELDS

    # Override the 'hostname' field so that it returns the FQDN instead as
    # this is used by Juju to reach that node.
    @classmethod
    def hostname(handler, node):
        return node.fqdn

    def read(self, request, system_id):
        """Read a specific Node."""
        return Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.VIEW)

    def update(self, request, system_id):
        """Update a specific Node.

        :param hostname: The new hostname for this node.
        :type hostname: basestring
        :param architecture: The new architecture for this node (see
            vocabulary `ARCHITECTURE`).
        :type architecture: basestring
        :param power_type: The new power type for this node (see
            vocabulary `POWER_TYPE`).  Note that if you set power_type to
            use the default value, power_parameters will be set to the empty
            string.  Available to admin users.
        :type power_type: basestring
        :param power_parameters_{param1}: The new value for the 'param1'
            power parameter.  Note that this is dynamic as the available
            parameters depend on the selected value of the Node's power_type.
            For instance, if the power_type is 'ether_wake', the only valid
            parameter is 'power_address' so one would want to pass 'myaddress'
            as the value of the 'power_parameters_power_address' parameter.
            Available to admin users.
        :type power_parameters_{param1}: basestring
        :param power_parameters_skip_check: Whether or not the new power
            parameters for this node should be checked against the expected
            power parameters for the node's power type ('true' or 'false').
            The default is 'false'.
        :type power_parameters_skip_validation: basestring
        """
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        data = get_overrided_query_dict(model_to_dict(node), request.data)

        Form = get_node_edit_form(request.user)
        form = Form(data, instance=node)
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
        :type user_data: base64-encoded basestring
        :param distro_series: If present, this parameter specifies the
            Ubuntu Release the node will use.
        :type distro_series: basestring

        Ideally we'd have MIME multipart and content-transfer-encoding etc.
        deal with the encapsulation of binary data, but couldn't make it work
        with the framework in reasonable time so went for a dumb, manual
        encoding instead.
        """
        user_data = request.POST.get('user_data', None)
        series = request.POST.get('distro_series', None)
        if user_data is not None:
            user_data = b64decode(user_data)
        if series is not None:
            node = Node.objects.get_node_or_404(
                system_id=system_id, user=request.user,
                perm=NODE_PERMISSION.EDIT)
            node.set_distro_series(series=series)
        nodes = Node.objects.start_nodes(
            [system_id], request.user, user_data=user_data)
        if len(nodes) == 0:
            raise PermissionDenied(
                "You are not allowed to start up this node.")
        return nodes[0]

    @operation(idempotent=False)
    def release(self, request, system_id):
        """Release a node.  Opposite of `NodesHandler.acquire`."""
        node = Node.objects.get_node_or_404(
            system_id=system_id, user=request.user, perm=NODE_PERMISSION.EDIT)
        node.set_distro_series(series='')
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

    Form = get_node_create_form(request.user)
    form = Form(altered_query_data)
    if form.is_valid():
        node = form.save()
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
        return create_node(request)

    @operation(idempotent=True)
    def is_registered(self, request):
        """Returns whether or not the given MAC address is registered within
        this MAAS (and attached to a non-retired node).

        :param mac_address: The mac address to be checked.
        :type mac_address: basestring
        :return: 'true' or 'false'.
        :rtype: basestring
        """
        mac_address = get_mandatory_param(request.GET, 'mac_address')
        return MACAddress.objects.filter(
            mac_address=mac_address).exclude(
                node__status=NODE_STATUS.RETIRED).exists()

    @operation(idempotent=False)
    def accept(self, request):
        """Accept a node's enlistment: not allowed to anonymous users."""
        raise Unauthorized("You must be logged in to accept nodes.")

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
        query.update(status=NODE_STATUS.FAILED_TESTS)
        # Note that Django doesn't call save() on updated nodes here,
        # but I don't think anything requires its effects anyway.

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


def extract_constraints(request_params):
    """Extract a dict of node allocation constraints from http parameters.

    :param request_params: Parameters submitted with the allocation request.
    :type request_params: :class:`django.http.QueryDict`
    :return: A mapping of applicable constraint names to their values.
    :rtype: :class:`dict`
    """
    constraints = {}
    for request_name in CONSTRAINTS_MAAS_MAP:
        if request_name in request_params:
            db_name = CONSTRAINTS_MAAS_MAP[request_name]
            constraints[db_name] = request_params[request_name]
    return constraints


class NodesHandler(OperationsHandler):
    """Manage the collection of all Nodes in the MAAS."""
    create = read = update = delete = None
    anonymous = AnonNodesHandler

    @operation(idempotent=False)
    def new(self, request):
        """Create a new Node.

        When a node has been added to MAAS by an admin MAAS user, it is
        ready for allocation to services running on the MAAS.
        The minimum data required is:
        architecture=<arch string> (e.g "i386/generic")
        mac_address=<value>
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

        :param mac_address: An optional list of MAC addresses.  Only
            nodes with matching MAC addresses will be returned.
        :type mac_address: iterable
        :param id: An optional list of system ids.  Only nodes with
            matching system ids will be returned.
        :type id: iterable
        """
        # Get filters from request.
        match_ids = get_optional_list(request.GET, 'id')
        match_macs = get_optional_list(request.GET, 'mac_address')
        if match_macs is not None:
            invalid_macs = [
                mac for mac in match_macs if mac_re.match(mac) is None]
            if len(invalid_macs) != 0:
                raise ValidationError(
                    "Invalid MAC address(es): %s" % ", ".join(invalid_macs))
        # Fetch nodes and apply filters.
        nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=match_ids)
        if match_macs is not None:
            nodes = nodes.filter(macaddress__mac_address__in=match_macs)
        # Prefetch related macaddresses, tags and nodegroups (plus
        # related interfaces).
        nodes = nodes.prefetch_related('macaddress_set__node')
        nodes = nodes.prefetch_related('tags')
        nodes = nodes.prefetch_related('nodegroup')
        nodes = nodes.prefetch_related('nodegroup__nodegroupinterface_set')
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
        """Acquire an available node for deployment."""
        node = Node.objects.get_available_node_for_acquisition(
            request.user, constraints=extract_constraints(request.data))
        if node is None:
            raise NodesNotAvailable("No matching node is available.")
        node.acquire(request.user, get_oauth_token(request))
        return node

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodeMacsHandler(OperationsHandler):
    """Manage MAC addresses for a given Node.

    This is where you manage the MAC addresses linked to a Node, including
    associating a new MAC address with the Node.

    The Node is identified by its system_id.
    """
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
    """Manage a MAC address.

    The MAC address object is identified by the system_id for the Node it
    is attached to, plus the MAC address itself.
    """
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


def get_file(handler, request):
    """Get a named file from the file storage.

    :param filename: The exact name of the file you want to get.
    :type filename: string
    :return: The file is returned in the response content.
    """
    filename = request.GET.get("filename", None)
    if not filename:
        raise MAASAPIBadRequest("Filename not supplied")
    try:
        db_file = FileStorage.objects.get(filename=filename)
    except FileStorage.DoesNotExist:
        raise MAASAPINotFound("File not found")
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

    get = operation(idempotent=True, exported_as='get')(get_file)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('files_handler', [])


class FilesHandler(OperationsHandler):
    """File management operations."""
    create = read = update = delete = None
    anonymous = AnonFilesHandler

    get = operation(idempotent=True, exported_as='get')(get_file)

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
        FileStorage.objects.save_file(filename, uploaded_file)
        return HttpResponse('', status=httplib.CREATED)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('files_handler', [])


def get_celery_credentials():
    """Return the credentials needed to connect to the broker."""
    celery_conf = app_or_default().conf
    return {
        'BROKER_URL': celery_conf.BROKER_URL,
    }


DISPLAYED_NODEGROUP_FIELDS = ('uuid', 'status', 'name')


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
        """Register a new `NodeGroup`.

        This method will use HTTP return codes to indicate the success of the
        call:

        - 200 (OK): the nodegroup has been accepted, the response will
          contain the RabbitMQ credentials in JSON format: e.g.:
          '{"BROKER_URL" = "amqp://guest:guest@localhost:5672//"}'
        - 202 (Accepted): the registration of the nodegroup has been accepted,
          it now needs to be validated by an administrator.  Please issue
          the same request later.
        - 403 (Forbidden): this nodegroup has been rejected.

        :param uuid: The UUID of the nodegroup.
        :type name: basestring
        :param name: The name of the nodegroup.
        :type name: basestring
        :param interfaces: The list of the interfaces' data.
        :type interface: json string containing a list of dictionaries with
            the data to initialize the interfaces.
            e.g.: '[{"ip_range_high": "192.168.168.254",
            "ip_range_low": "192.168.168.1", "broadcast_ip":
            "192.168.168.255", "ip": "192.168.168.18", "subnet_mask":
            "255.255.255.0", "router_ip": "192.168.168.1", "interface":
            "eth0"}]'
        """
        uuid = get_mandatory_param(request.data, 'uuid')
        existing_nodegroup = get_one(NodeGroup.objects.filter(uuid=uuid))
        if existing_nodegroup is None:
            master = NodeGroup.objects.ensure_master()
            # Does master.uuid look like it's a proper uuid?
            if master.uuid in ('master', ''):
                # Master nodegroup not yet configured, configure it.
                form = NodeGroupWithInterfacesForm(
                    data=request.data, instance=master)
                if form.is_valid():
                    form.save()
                    return get_celery_credentials()
                else:
                    raise ValidationError(form.errors)
            else:
                # This nodegroup (identified by its uuid), does not exist yet,
                # create it if the data validates.
                form = NodeGroupWithInterfacesForm(
                    data=request.data, status=NODEGROUP_STATUS.PENDING)
                if form.is_valid():
                    form.save()
                    return HttpResponse(
                        "Cluster registered.  Awaiting admin approval.",
                        status=httplib.ACCEPTED)
                else:
                    raise ValidationError(form.errors)
        else:
            if existing_nodegroup.status == NODEGROUP_STATUS.ACCEPTED:
                # The nodegroup exists and is validated, return the RabbitMQ
                return get_celery_credentials()
            elif existing_nodegroup.status == NODEGROUP_STATUS.REJECTED:
                raise PermissionDenied('Rejected cluster.')
            elif existing_nodegroup.status == NODEGROUP_STATUS.PENDING:
                return HttpResponse(
                    "Awaiting admin approval.", status=httplib.ACCEPTED)


class NodeGroupsHandler(OperationsHandler):
    """Manage NodeGroups."""
    anonymous = AnonNodeGroupsHandler
    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    @operation(idempotent=True)
    def list(self, request):
        """List of node groups."""
        return NodeGroup.objects.all()

    @operation(idempotent=False)
    def accept(self, request):
        """Accept nodegroup enlistment(s).

        :param uuid: The UUID (or list of UUIDs) of the nodegroup(s) to accept.
        :type name: basestring (or list of basestrings)

        This method is reserved to admin users.
        """
        if request.user.is_superuser:
            uuids = request.data.getlist('uuid')
            for uuid in uuids:
                nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
                nodegroup.accept()
            return HttpResponse("Nodegroup(s) accepted.", status=httplib.OK)
        else:
            raise PermissionDenied("That method is reserved to admin users.")

    @operation(idempotent=False)
    def import_boot_images(self, request):
        """Import the boot images on all the accepted cluster controllers."""
        if not request.user.is_superuser:
            raise PermissionDenied("That method is reserved to admin users.")
        NodeGroup.objects.import_boot_images_accepted_clusters()
        return HttpResponse(
            "Import of boot images started on all cluster controllers",
            status=httplib.OK)

    @operation(idempotent=False)
    def reject(self, request):
        """Reject nodegroup enlistment(s).

        :param uuid: The UUID (or list of UUIDs) of the nodegroup(s) to reject.
        :type name: basestring (or list of basestrings)

        This method is reserved to admin users.
        """
        if request.user.is_superuser:
            uuids = request.data.getlist('uuid')
            for uuid in uuids:
                nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
                nodegroup.reject()
            return HttpResponse("Nodegroup(s) rejected.", status=httplib.OK)
        else:
            raise PermissionDenied("That method is reserved to admin users.")

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

    create = update = delete = None
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
        new_leases = DHCPLease.objects.update_leases(nodegroup, leases)
        if len(new_leases) > 0:
            nodegroup.add_dhcp_host_maps(
                {ip: leases[ip] for ip in new_leases if ip in leases})
        return HttpResponse("Leases updated.", status=httplib.OK)

    @operation(idempotent=False)
    def import_boot_images(self, request, uuid):
        """Import the pxe files on this cluster controller."""
        if not request.user.is_superuser:
            raise PermissionDenied("That method is reserved to admin users.")
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

    # node_hardware_details is actually idempotent, however:
    # a) We expect to get a list of system_ids which is quite long (~100 ids,
    #    each 40 bytes, is 4000 bytes), which is a bit too long for a URL.
    # b) MAASClient.get() just uses urlencode(params) but urlencode ends up
    #    just calling str(lst) and encoding that, which transforms te list of
    #    ids into something unusable. .post() does the right thing.
    @operation(idempotent=False)
    def node_hardware_details(self, request, uuid):
        """Return specific hardware_details for each node specified.

        For security purposes we do:

        a) Requests are only fulfilled for the worker assigned to the
           nodegroup.
        b) Requests for nodes that are not part of the nodegroup are just
           ignored.

        This API may be removed in the future when hardware details are moved
        to be stored in the cluster controllers (nodegroup) instead of the
        master controller.
        """
        system_ids = get_list_from_dict_or_multidict(
            request.data, 'system_ids', [])
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        if not request.user.is_superuser:
            check_nodegroup_access(request, nodegroup)
        value_list = Node.objects.filter(
            system_id__in=system_ids, nodegroup=nodegroup
            ).values_list('system_id', 'hardware_details')
        return HttpResponse(
            json.dumps(list(value_list)), content_type='application/json')


DISPLAYED_NODEGROUP_FIELDS = (
    'ip', 'management', 'interface', 'subnet_mask',
    'broadcast_ip', 'ip_range_low', 'ip_range_high')


class NodeGroupInterfacesHandler(OperationsHandler):
    """Manage NodeGroupInterfaces.

    A NodeGroupInterface is a network interface attached to a cluster
    controller, with its network properties.
    """
    create = read = update = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    @operation(idempotent=True)
    def list(self, request, uuid):
        """List of NodeGroupInterfaces of a NodeGroup."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        return NodeGroupInterface.objects.filter(nodegroup=nodegroup)

    @operation(idempotent=False)
    def new(self, request, uuid):
        """Create a new NodeGroupInterface for this NodeGroup.

        :param ip: Static IP of the interface.
        :type ip: basestring (IP Address)
        :param interface: Name of the interface.
        :type interface: basestring
        :param management: The service(s) MAAS should manage on this interface.
        :type management: Vocabulary `NODEGROUPINTERFACE_MANAGEMENT`
        :param subnet_mask: Subnet mask, e.g. 255.0.0.0.
        :type subnet_mask: basestring (IP Address)
        :param broadcast_ip: Broadcast address for this subnet.
        :type broadcast_ip: basestring (IP Address)
        :param router_ip: Address of default gateway.
        :type router_ip: basestring (IP Address)
        :param ip_range_low: Lowest IP address to assign to clients.
        :type ip_range_low: basestring (IP Address)
        :param ip_range_high: Highest IP address to assign to clients.
        :type ip_range_high: basestring (IP Address)
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        form = NodeGroupInterfaceForm(request.data)
        if form.is_valid():
            return form.save(
                nodegroup=nodegroup)
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
    create = delete = None
    fields = DISPLAYED_NODEGROUP_FIELDS

    def read(self, request, uuid, interface):
        """List of NodeGroupInterfaces of a NodeGroup."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        nodegroupinterface = get_object_or_404(
            NodeGroupInterface, nodegroup=nodegroup, interface=interface)
        return nodegroupinterface

    def update(self, request, uuid, interface):
        """Update a specific NodeGroupInterface.

        :param ip: Static IP of the interface.
        :type ip: basestring (IP Address)
        :param interface: Name of the interface.
        :type interface: basestring
        :param management: The service(s) MAAS should manage on this interface.
        :type management: Vocabulary `NODEGROUPINTERFACE_MANAGEMENT`
        :param subnet_mask: Subnet mask, e.g. 255.0.0.0.
        :type subnet_mask: basestring (IP Address)
        :param broadcast_ip: Broadcast address for this subnet.
        :type broadcast_ip: basestring (IP Address)
        :param router_ip: Address of default gateway.
        :type router_ip: basestring (IP Address)
        :param ip_range_low: Lowest IP address to assign to clients.
        :type ip_range_low: basestring (IP Address)
        :param ip_range_high: Highest IP address to assign to clients.
        :type ip_range_high: basestring (IP Address)
        """
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        nodegroupinterface = get_object_or_404(
            NodeGroupInterface, nodegroup=nodegroup, interface=interface)
        data = get_overrided_query_dict(
            model_to_dict(nodegroupinterface), request.data)
        form = NodeGroupInterfaceForm(data, instance=nodegroupinterface)
        if form.is_valid():
            return form.save()
        else:
            raise ValidationError(form.errors)

    def delete(self, request, uuid, interface):
        """Delete a specific NodeGroupInterface."""
        nodegroup = get_object_or_404(NodeGroup, uuid=uuid)
        nodegroupinterface = get_object_or_404(
            NodeGroupInterface, nodegroup=nodegroup, interface=interface)
        nodegroupinterface.delete()
        return rc.DELETED

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
        :type token_key: basestring
        """
        profile = request.user.get_profile()
        token_key = get_mandatory_param(request.data, 'token_key')
        profile.delete_authorisation_token(token_key)
        return rc.DELETED

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('account_handler', [])


class TagHandler(OperationsHandler):
    """Manage individual Tags.

    Tags are properties that can be associated with a Node and serve as
    criteria for selecting and allocating nodes.

    A Tag is identified by its name.
    """
    create = None
    model = Tag
    fields = (
        'name',
        'definition',
        'comment',
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
        tag = Tag.objects.get_tag_or_404(name=name, user=request.user,
            to_edit=True)
        model_dict = model_to_dict(tag)
        data = get_overrided_query_dict(model_dict, request.data)
        form = TagForm(data, instance=tag)
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
        tag = Tag.objects.get_tag_or_404(name=name,
            user=request.user, to_edit=True)
        tag.delete()
        return rc.DELETED

    @operation(idempotent=True)
    def nodes(self, request, name):
        """Get the list of nodes that have this tag."""
        return Tag.objects.get_nodes(name, user=request.user)

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
    """Manage collection of Tags."""
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


class MAASHandler(OperationsHandler):
    """Manage the MAAS' itself."""
    create = read = update = delete = None

    @operation(idempotent=False)
    def set_config(self, request):
        """Set a config value.

        :param name: The name of the config item to be set.
        :type name: basestring
        :param name: The value of the config item to be set.
        :type value: json object
        """
        name = get_mandatory_param(
            request.data, 'name', validators.String(min=1))
        value = get_mandatory_param(request.data, 'value')
        Config.objects.set_config(name, value)
        return rc.ALL_OK

    @operation(idempotent=True)
    def get_config(self, request):
        """Get a config value.

        :param name: The name of the config item to be retrieved.
        :type name: basestring
        """
        name = get_mandatory_param(request.GET, 'name')
        value = Config.objects.get_config(name)
        return HttpResponse(json.dumps(value), content_type='application/json')


# Title section for the API documentation.  Matches in style, format,
# etc. whatever render_api_docs() produces, so that you can concatenate
# the two.
api_doc_title = dedent("""
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
        for (http_method, operation), function in sorted(exports):
            line("``%s %s``" % (http_method, uri_template), end="")
            if operation is not None:
                line(" ``op=%s``" % operation)
            line()
            docstring = getdoc(function)
            if docstring is not None:
                for docline in docstring.splitlines():
                    line("  ", docline, sep="")
                line()

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


def get_boot_purpose(node):
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
    """
    node = get_node_from_mac_string(request.GET.get('mac', None))

    if node:
        arch, subarch = node.architecture.split('/')
        preseed_url = compose_preseed_url(node)
        # The node's hostname may include a domain, but we ignore that
        # and use the one from the nodegroup instead.
        hostname = strip_domain(node.hostname)
        domain = node.nodegroup.name
    else:
        try:
            pxelinux_arch = request.GET['arch']
        except KeyError:
            if 'mac' in request.GET:
                # Request was pxelinux.cfg/01-<mac>, so attempt fall back
                # to pxelinux.cfg/default-<arch>-<subarch> for arch detection.
                return HttpResponse(status=httplib.NO_CONTENT)
            else:
                # Request has already fallen back, so if arch is still not
                # provided then use i386.
                arch = ARCHITECTURE.i386.split('/')[0]
        else:
            # Map from pxelinux namespace architecture names to MAAS namespace
            # architecture names. If this gets bigger, an external lookup table
            # would make sense. But here is fine for something as trivial as it
            # is right now.
            if pxelinux_arch == 'arm':
                arch = 'armhf'
            else:
                arch = pxelinux_arch

        # Use subarch if supplied; otherwise assume 'generic'.
        try:
            pxelinux_subarch = request.GET['subarch']
        except KeyError:
            subarch = 'generic'
        else:
            # Map from pxelinux namespace subarchitecture names to MAAS
            # namespace subarchitecture names. Right now this happens to be a
            # 1-1 mapping.
            subarch = pxelinux_subarch

        preseed_url = compose_enlistment_preseed_url()
        hostname = 'maas-enlist'
        domain = Config.objects.get_config('enlistment_domain')

    if node is None or node.status == NODE_STATUS.COMMISSIONING:
        series = Config.objects.get_config('commissioning_distro_series')
    else:
        series = node.get_distro_series()

    purpose = get_boot_purpose(node)
    server_address = get_maas_facing_server_address()
    cluster_address = get_mandatory_param(request.GET, "local")

    params = KernelParameters(
        arch=arch, subarch=subarch, release=series, purpose=purpose,
        hostname=hostname, domain=domain, preseed_url=preseed_url,
        log_host=server_address, fs_host=cluster_address)

    return HttpResponse(
        json.dumps(params._asdict()),
        content_type="application/json")


class BootImagesHandler(OperationsHandler):

    create = replace = update = delete = None

    @classmethod
    def resource_uri(cls):
        return ('boot_images_handler', [])

    @operation(idempotent=False)
    def report_boot_images(self, request):
        """Report images available to net-boot nodes from.

        :param images: A list of dicts, each describing a boot image with
            these properties: `architecture`, `subarchitecture`, `release`,
            `purpose`, all as in the code that determines TFTP paths for
            these images.
        """
        nodegroup_uuid = get_mandatory_param(request.data, "nodegroup")
        nodegroup = get_object_or_404(NodeGroup, uuid=nodegroup_uuid)
        check_nodegroup_access(request, nodegroup)
        images = json.loads(get_mandatory_param(request.data, 'images'))

        for image in images:
            BootImage.objects.register_image(
                nodegroup=nodegroup,
                architecture=image['architecture'],
                subarchitecture=image.get('subarchitecture', 'generic'),
                release=image['release'],
                purpose=image['purpose'])

        # Work out if any nodegroups are missing images.
        nodegroup_ids_with_images = BootImage.objects.values_list(
            "nodegroup_id", flat=True)
        nodegroups_missing_images = NodeGroup.objects.exclude(
            id__in=nodegroup_ids_with_images).filter(
                status=NODEGROUP_STATUS.ACCEPTED)
        if nodegroups_missing_images.exists():
            warning = dedent("""\
                Some cluster controllers are missing boot images.  Either the
                maas-import-pxe-files script has not run yet, or it failed.

                Try running it manually on the affected
                <a href="%s#accepted-clusters">cluster controllers.</a>
                If it succeeds, this message will go away within 5 minutes.
                """ % absolute_reverse("settings"))
            register_persistent_error(COMPONENT.IMPORT_PXE_FILES, warning)
        else:
            discard_persistent_error(COMPONENT.IMPORT_PXE_FILES)

        return HttpResponse("OK")


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
    # Make all URIs absolute. Clients - maas-cli in particular - expect that
    # all handler URIs are absolute, not just paths. The handler URIs returned
    # by describe_resource() are relative paths.
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
