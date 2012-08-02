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
    "api_doc",
    "api_doc_title",
    "generate_api_doc",
    "get_oauth_token",
    "AccountHandler",
    "AnonNodesHandler",
    "FilesHandler",
    "NodeGroupsHandler",
    "NodeHandler",
    "NodesHandler",
    "NodeMacHandler",
    "NodeMacsHandler",
    "pxeconfig",
    ]

from base64 import b64decode
from datetime import (
    datetime,
    timedelta,
    )
import httplib
import json
import sys
from textwrap import dedent
import types

from django.conf import settings
from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
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
from maasserver.enum import (
    NODE_PERMISSION,
    NODE_STATUS,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodesNotAvailable,
    NodeStateViolation,
    Unauthorized,
    )
from maasserver.fields import validate_mac
from maasserver.forms import (
    get_node_create_form,
    get_node_edit_form,
    )
from maasserver.models import (
    Config,
    DHCPLease,
    FileStorage,
    MACAddress,
    Node,
    NodeGroup,
    )
from maasserver.utils import absolute_reverse
from piston.doc import generate_doc
from piston.handler import (
    AnonymousBaseHandler,
    BaseHandler,
    HandlerMetaClass,
    )
from piston.models import Token
from piston.resource import Resource
from piston.utils import rc


dispatch_methods = {
    'GET': 'read',
    'POST': 'create',
    'PUT': 'update',
    'DELETE': 'delete',
    }


class RestrictedResource(Resource):

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


def api_exported(method='POST', exported_as=None):
    """Decorator to make a method available on the API.

    :param method: The HTTP method over which to export the operation.
    :param exported_as: Optional operation name; defaults to the name of the
        exported method.

    See also _`api_operations`.
    """
    def _decorator(func):
        if method not in dispatch_methods:
            raise ValueError("Invalid method: '%s'" % method)
        if exported_as is None:
            func._api_exported = {method: func.__name__}
        else:
            func._api_exported = {method: exported_as}
        if func._api_exported.get(method) == dispatch_methods.get(method):
            raise ValueError(
                "Cannot define a '%s' operation." % dispatch_methods.get(
                    method))
        return func
    return _decorator


# The parameter used to specify the requested operation for POST API calls.
OP_PARAM = 'op'


def is_api_exported(thing, method='POST'):
    # Check for functions and methods; the latter may be from base classes.
    op_types = types.FunctionType, types.MethodType
    return (
        isinstance(thing, op_types) and
        getattr(thing, "_api_exported", None) is not None and
        getattr(thing, "_api_exported", None).get(method, None) is not None)


# Define a method that will route requests to the methods registered in
# handler._available_api_methods.
def perform_api_operation(handler, request, method='POST', *args, **kwargs):
    if method == 'POST':
        data = request.POST
    else:
        data = request.GET
    op = data.get(OP_PARAM, None)
    if not isinstance(op, unicode):
        return HttpResponseBadRequest("Unknown operation.")
    elif method not in handler._available_api_methods:
        return HttpResponseBadRequest("Unknown operation: '%s'." % op)
    elif op not in handler._available_api_methods[method]:
        return HttpResponseBadRequest("Unknown operation: '%s'." % op)
    else:
        method = handler._available_api_methods[method][op]
        return method(handler, request, *args, **kwargs)


def api_operations(cls):
    """Class decorator (PEP 3129) to be used on piston-based handler classes
    (i.e. classes inheriting from piston.handler.BaseHandler).  It will add
    the required methods {'create','read','update','delete} to the class.
    These methods (called by piston to handle POST/GET/PUT/DELETE requests),
    will route requests to methods decorated with
    @api_exported(method={'POST','GET','PUT','DELETE'} depending on the
    operation requested using the 'op' parameter.

    E.g.:

    >>> @api_operations
    >>> class MyHandler(BaseHandler):
    >>>
    >>>    @api_exported(method='POST', exported_as='exported_post_name')
    >>>    def do_x(self, request):
    >>>        # process request...
    >>>
    >>>    @api_exported(method='GET')
    >>>    def do_y(self, request):
    >>>        # process request...

    MyHandler's method 'do_x' will service POST requests with
    'op=exported_post_name' in its request parameters.

    POST /api/path/to/MyHandler/
    op=exported_post_name&param1=1

    MyHandler's method 'do_y' will service GET requests with
    'op=do_y' in its request parameters.

    GET /api/path/to/MyHandler/?op=do_y&param1=1

    """
    # Compute the list of methods ('GET', 'POST', etc.) that need to be
    # overriden.
    overriden_methods = set()
    for name, value in vars(cls).items():
        overriden_methods.update(getattr(value, '_api_exported', {}))
    # Override the appropriate methods with a 'dispatcher' method.
    for method in overriden_methods:
        operations = {
            name: value
            for name, value in vars(cls).items()
            if is_api_exported(value, method)}
        cls._available_api_methods = getattr(
            cls, "_available_api_methods", {}).copy()
        cls._available_api_methods[method] = {
            op._api_exported[method]: op
                for name, op in operations.items()
                if method in op._api_exported}

        def dispatcher(self, request, *args, **kwargs):
            return perform_api_operation(
                self, request, request.method, *args, **kwargs)

        method_name = str(dispatch_methods[method])
        dispatcher.__name__ = method_name
        dispatcher.__doc__ = (
            "The actual operation to execute depends on the value of the '%s' "
            "parameter:\n\n" % OP_PARAM)
        dispatcher.__doc__ += "\n".join(
            "- Operation '%s' (op=%s):\n\t%s" % (name, name, op.__doc__)
            for name, op in cls._available_api_methods[method].items())

        # Add {'create','read','update','delete'} method.
        setattr(cls, method_name, dispatcher)
    return cls


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
    'power_parameters',
    )


@api_operations
class NodeHandler(BaseHandler):
    """Manage individual Nodes."""
    allowed_methods = ('GET', 'DELETE', 'POST', 'PUT')
    model = Node
    fields = DISPLAYED_NODE_FIELDS

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

    @api_exported('POST')
    def stop(self, request, system_id):
        """Shut down a node."""
        nodes = Node.objects.stop_nodes([system_id], request.user)
        if len(nodes) == 0:
            raise PermissionDenied(
                "You are not allowed to shut down this node.")
        return nodes[0]

    @api_exported('POST')
    def start(self, request, system_id):
        """Power up a node.

        The user_data parameter, if set in the POST data, is taken as
        base64-encoded binary data.

        Ideally we'd have MIME multipart and content-transfer-encoding etc.
        deal with the encapsulation of binary data, but couldn't make it work
        with the framework in reasonable time so went for a dumb, manual
        encoding instead.
        """
        user_data = request.POST.get('user_data', None)
        if user_data is not None:
            user_data = b64decode(user_data)
        nodes = Node.objects.start_nodes(
            [system_id], request.user, user_data=user_data)
        if len(nodes) == 0:
            raise PermissionDenied(
                "You are not allowed to start up this node.")
        return nodes[0]

    @api_exported('POST')
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


def create_node(request):
    """Service an http request to create a node.

    The node will be in the Declared state.

    :param request: The http request for this node to be created.
    :return: A `Node`.
    :rtype: :class:`maasserver.models.Node`.
    :raises: ValidationError
    """
    Form = get_node_create_form(request.user)
    form = Form(request.data)
    if form.is_valid():
        return form.save()
    else:
        raise ValidationError(form.errors)


@api_operations
class AnonNodesHandler(AnonymousBaseHandler):
    """Create Nodes."""
    allowed_methods = ('GET', 'POST',)
    fields = DISPLAYED_NODE_FIELDS

    @api_exported('POST')
    def new(self, request):
        """Create a new Node.

        Adding a server to a MAAS puts it on a path that will wipe its disks
        and re-install its operating system.  In anonymous enlistment and when
        the enlistment is done by a non-admin, the node is held in the
        "Declared" state for approval by a MAAS admin.
        """
        return create_node(request)

    @api_exported('GET')
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

    @api_exported('POST')
    def accept(self, request):
        """Accept a node's enlistment: not allowed to anonymous users."""
        raise Unauthorized("You must be logged in to accept nodes.")

    @api_exported("POST")
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
    name = request_params.get('name', None)
    if name is None:
        return {}
    else:
        return {'name': name}


@api_operations
class NodesHandler(BaseHandler):
    """Manage collection of Nodes."""
    allowed_methods = ('GET', 'POST',)
    anonymous = AnonNodesHandler

    @api_exported('POST')
    def new(self, request):
        """Create a new Node.

        When a node has been added to MAAS by an admin MAAS user, it is
        ready for allocation to services running on the MAAS.
        """
        node = create_node(request)
        if request.user.is_superuser:
            node.accept_enlistment(request.user)
        return node

    @api_exported('POST')
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
        existing_ids = set(Node.objects.filter().values_list(
            'system_id', flat=True))
        if len(existing_ids) < len(system_ids):
            raise MAASAPIBadRequest(
                "Unknown node(s): %s." % ', '.join(system_ids - existing_ids))
        # Make sure that the user has the required permission.
        nodes = Node.objects.get_nodes(
            request.user, perm=NODE_PERMISSION.ADMIN, ids=system_ids)
        ids = set(node.system_id for node in nodes)
        if len(nodes) < len(system_ids):
            raise PermissionDenied(
                "You don't have the required permission to accept the "
                "following node(s): %s." % (
                    ', '.join(system_ids - ids)))
        return filter(
            None, [node.accept_enlistment(request.user) for node in nodes])

    @api_exported('GET')
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
        # Fetch nodes and apply filters.
        nodes = Node.objects.get_nodes(
            request.user, NODE_PERMISSION.VIEW, ids=match_ids)
        if match_macs is not None:
            nodes = nodes.filter(macaddress__mac_address__in=match_macs)
        return nodes.order_by('id')

    @api_exported('GET')
    def list_allocated(self, request):
        """Fetch Nodes that were allocated to the User/oauth token."""
        token = get_oauth_token(request)
        match_ids = get_optional_list(request.GET, 'id')
        nodes = Node.objects.get_allocated_visible_nodes(token, match_ids)
        return nodes.order_by('id')

    @api_exported('POST')
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


class NodeMacsHandler(BaseHandler):
    """
    Manage all the MAC addresses linked to a Node / Create a new MAC address
    for a Node.

    """
    allowed_methods = ('GET', 'POST',)

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


class NodeMacHandler(BaseHandler):
    """Manage a MAC address linked to a Node."""
    allowed_methods = ('GET', 'DELETE')
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
    return HttpResponse(db_file.data.read(), status=httplib.OK)


@api_operations
class AnonFilesHandler(AnonymousBaseHandler):
    """Anonymous file operations.

    This is needed for Juju. The story goes something like this:

    - The Juju provider will upload a file using an "unguessable" name.

    - The name of this file (or its URL) will be shared with all the agents in
      the environment. They cannot modify the file, but they can access it
      without credentials.

    """
    allowed_methods = ('GET',)

    get = api_exported('GET', exported_as='get')(get_file)


@api_operations
class FilesHandler(BaseHandler):
    """File management operations."""
    allowed_methods = ('GET', 'POST',)
    anonymous = AnonFilesHandler

    get = api_exported('GET', exported_as='get')(get_file)

    @api_exported('POST')
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


@api_operations
class NodeGroupsHandler(BaseHandler):
    """Node-groups API.  Lists the registered node groups."""

    allowed_methods = ('GET', )

    def read(self, request):
        """Index of node groups."""
        return HttpResponse(sorted(
            [nodegroup.name for nodegroup in NodeGroup.objects.all()]))

    @classmethod
    def resource_uri(cls):
        return ('nodegroups_handler', [])


@api_operations
class NodeGroupHandler(BaseHandler):
    """Node-group API."""

    allowed_methods = ('GET', 'POST')
    fields = ('name', )

    def read(self, request, name):
        """GET a node group."""
        return get_object_or_404(NodeGroup, name=name)

    @classmethod
    def resource_uri(cls, nodegroup):
        if nodegroup is None:
            name = 'name'
        else:
            name = nodegroup.name
        return ('nodegroup_handler', [name])

    @api_exported('POST')
    def update_leases(self, request, name):
        leases = get_mandatory_param(request.data, 'leases')
        nodegroup = get_object_or_404(NodeGroup, name=name)
        DHCPLease.objects.update_leases(nodegroup, json.loads(leases))
        return HttpResponse("Leases updated.", status=httplib.OK)


@api_operations
class AccountHandler(BaseHandler):
    """Manage the current logged-in user."""
    allowed_methods = ('POST',)

    @api_exported('POST')
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

    @api_exported('POST')
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


@api_operations
class MAASHandler(BaseHandler):
    """Manage the MAAS' itself."""
    allowed_methods = ('POST', 'GET')

    @api_exported('POST')
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

    @api_exported('GET')
    def get_config(self, request):
        """Get a config value.

        :param name: The name of the config item to be retrieved.
        :type name: basestring
        """
        name = get_mandatory_param(request.GET, 'name')
        value = Config.objects.get_config(name)
        return HttpResponse(json.dumps(value), content_type='application/json')


# Title section for the API documentation.  Matches in style, format,
# etc. whatever generate_api_doc() produces, so that you can concatenate
# the two.
api_doc_title = dedent("""
    ========
    MAAS API
    ========
    """.lstrip('\n'))


def generate_api_doc():
    """Generate ReST documentation for the REST API.

    This module's docstring forms the head of the documentation; details of
    the API methods follow.

    :return: Documentation, in ReST, for the API.
    :rtype: :class:`unicode`
    """

    # Fetch all the API Handlers (objects with the class
    # HandlerMetaClass).
    module = sys.modules[__name__]

    all = [getattr(module, name) for name in module.__all__]
    handlers = [obj for obj in all if isinstance(obj, HandlerMetaClass)]

    # Make sure each handler defines a 'resource_uri' method (this is
    # easily forgotten and essential to have a proper documentation).
    for handler in handlers:
        sentinel = object()
        resource_uri = getattr(handler, "resource_uri", sentinel)
        assert resource_uri is not sentinel, "Missing resource_uri in %s" % (
            handler.__name__)

    docs = [generate_doc(handler) for handler in handlers]

    messages = [
        __doc__.strip(),
        '',
        '',
        'Operations',
        '----------',
        '',
        ]
    for doc in docs:
        for method in doc.get_methods():
            messages.append(
                "%s %s\n  %s\n" % (
                    method.http_name, doc.resource_uri_template,
                    method.doc))
    return '\n'.join(messages)


def reST_to_html_fragment(a_str):
    parts = core.publish_parts(source=a_str, writer_name='html')
    return parts['body_pre_docinfo'] + parts['fragment']


_API_DOC = None


def api_doc(request):
    """Get ReST documentation for the REST API."""
    # Generate the documentation and keep it cached.  Note that we can't do
    # that at the module level because the API doc generation needs Django
    # fully initialized.
    global _API_DOC
    if _API_DOC is None:
        _API_DOC = generate_api_doc()
    return render_to_response(
        'maasserver/api_doc.html',
        {'doc': reST_to_html_fragment(generate_api_doc())},
        context_instance=RequestContext(request))


def compose_enlistment_preseed_url():
    """Compose enlistment preseed URL."""
    # Always uses the latest version of the metadata API.
    version = 'latest'
    return absolute_reverse(
        'metadata-enlist-preseed', args=[version],
        query={'op': 'get_enlist_preseed'})


def compose_preseed_url(node):
    """Compose a metadata URL for `node`'s preseed data."""
    # Always uses the latest version of the metadata API.
    version = 'latest'
    return absolute_reverse(
        'metadata-node-by-id', args=[version, node.system_id],
        query={'op': 'get_preseed'})


def compose_preseed_kernel_opt(node):
    """Compose a kernel option for preseed URL for given `node`.

    :param mac_address: A `Node`, or `None`.
    """
    if node is None:
        preseed_url = compose_enlistment_preseed_url()
    else:
        preseed_url = compose_preseed_url(node)
    return "auto url=%s" % preseed_url


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


def pxeconfig(request):
    """Get the PXE configuration given a node's details.

    :param mac: MAC address to produce a boot configuration for.  This
        parameter is optional.  If it is not given, the configuration
        will be the "default" one which boots into an enlistment image.
    :param arch: Main machine architecture.
    :param subarch: Sub-architecture, or "generic" if there is none.
    :param append: Additional parameters to append to the kernel command
        line.
    """
    mac = request.GET.get('mac', None)
    arch = get_mandatory_param(request.GET, 'arch')
    subarch = request.GET.get('subarch', 'generic')
    append = get_mandatory_param(request.GET, 'append')

    # See if we have a record of this MAC address, and thus node.
    try:
        macaddress = MACAddress.objects.get(mac_address=mac)
    except MACAddress.DoesNotExist:
        macaddress = node = None
    else:
        node = macaddress.node

    # In addition to the "append" parameter, also add a URL for the
    # node's preseed to the kernel command line.
    append = "%s %s" % (append, compose_preseed_kernel_opt(node))

    # XXX: allenap 2012-07-31 bug=1013146: 'precise' is hardcoded here.
    release = "precise"

    params = dict(
        arch=arch, subarch=subarch, release=release,
        purpose=get_boot_purpose(node), append=append)

    return HttpResponse(
        json.dumps(params), content_type="application/json")
