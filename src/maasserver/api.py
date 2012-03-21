# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "api_doc",
    "extract_oauth_key",
    "generate_api_doc",
    "AccountHandler",
    "AnonNodesHandler",
    "FilesHandler",
    "NodeHandler",
    "NodesHandler",
    "NodeMacHandler",
    "NodeMacsHandler",
    ]

from base64 import b64decode
import httplib
import json
import sys
import types

from django.core.exceptions import ValidationError
from django.http import (
    HttpResponse,
    HttpResponseBadRequest,
    )
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from docutils import core
from formencode import validators
from formencode.validators import Invalid
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodesNotAvailable,
    NodeStateViolation,
    PermissionDenied,
    )
from maasserver.fields import validate_mac
from maasserver.forms import NodeWithMACAddressesForm
from maasserver.models import (
    Config,
    FileStorage,
    MACAddress,
    Node,
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    )
from piston.doc import generate_doc
from piston.handler import (
    AnonymousBaseHandler,
    BaseHandler,
    HandlerMetaClass,
    )
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


def api_exported(operation_name=True, method='POST'):
    def _decorator(func):
        if method not in dispatch_methods:
            raise ValueError("Invalid method: '%s'" % method)
        if operation_name == dispatch_methods.get(method):
            raise ValueError(
                "Cannot define a '%s' operation." % dispatch_methods.get(
                    method))
        func._api_exported = {method: operation_name}
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
    >>>    @api_exported('exported_post_name', method='POST')
    >>>    def do_x(self, request):
    >>>        # process request...
    >>>
    >>>    @api_exported('exported_get_name', method='GET')
    >>>    def do_y(self, request):
    >>>        # process request...

    MyHandler's method 'do_x' will service POST requests with
    'op=exported_post_name' in its request parameters.

    POST /api/path/to/MyHandler/
    op=exported_post_name&param1=1

    MyHandler's method 'do_y' will service GET requests with
    'op=exported_get_name' in its request parameters.

    GET /api/path/to/MyHandler/?op=exported_get_name&param1=1

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
            (name if op._api_exported[method] is True
                else op._api_exported[method]): op
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


def extract_oauth_key(auth_data):
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


NODE_FIELDS = (
    'system_id', 'hostname', ('macaddress_set', ('mac_address',)),
    'architecture', 'status')


@api_operations
class NodeHandler(BaseHandler):
    """Manage individual Nodes."""
    allowed_methods = ('GET', 'DELETE', 'POST', 'PUT')
    model = Node
    fields = NODE_FIELDS

    def read(self, request, system_id):
        """Read a specific Node."""
        return Node.objects.get_visible_node_or_404(
            system_id=system_id, user=request.user)

    def update(self, request, system_id):
        """Update a specific Node."""
        node = Node.objects.get_visible_node_or_404(
            system_id=system_id, user=request.user)
        for key, value in request.data.items():
            setattr(node, key, value)
        node.full_clean()
        node.save()
        return node

    def delete(self, request, system_id):
        """Delete a specific Node."""
        node = Node.objects.get_visible_node_or_404(
            system_id=system_id, user=request.user)
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

    @api_exported('stop', 'POST')
    def stop(self, request, system_id):
        """Shut down a node."""
        nodes = Node.objects.stop_nodes([system_id], request.user)
        if len(nodes) == 0:
            raise PermissionDenied(
                "You are not allowed to shut down this node.")
        return nodes[0]

    @api_exported('start', 'POST')
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

    @api_exported('release', 'POST')
    def release(self, request, system_id):
        """Release a node.  Opposite of `NodesHandler.acquire`."""
        node = Node.objects.get_visible_node_or_404(
            system_id=system_id, user=request.user)
        if node.status == NODE_STATUS.READY:
            # Nothing to do.  This may be a redundant retry, and the
            # postcondition is achieved, so call this success.
            pass
        elif node.status in [NODE_STATUS.ALLOCATED, NODE_STATUS.RESERVED]:
            node.release()
            node.save()
        else:
            raise NodeStateViolation(
                "Node cannot be released in its current state ('%s')."
                % NODE_STATUS_CHOICES_DICT.get(node.status, "UNKNOWN"))
        return node


def create_node(request):
    form = NodeWithMACAddressesForm(request.data)
    if form.is_valid():
        node = form.save()
        return node
    else:
        return HttpResponseBadRequest(
            form.errors, content_type='application/json')


@api_operations
class AnonNodesHandler(AnonymousBaseHandler):
    """Create Nodes."""
    allowed_methods = ('POST',)
    fields = NODE_FIELDS

    @api_exported('new', 'POST')
    def new(self, request):
        """Create a new Node."""
        return create_node(request)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


@api_operations
class NodesHandler(BaseHandler):
    """Manage collection of Nodes."""
    allowed_methods = ('GET', 'POST',)
    anonymous = AnonNodesHandler

    @api_exported('new', 'POST')
    def new(self, request):
        """Create a new Node."""
        return create_node(request)

    @api_exported('list', 'GET')
    def list(self, request):
        """List Nodes visible to the user, optionally filtered by id."""
        match_ids = request.GET.getlist('id')
        if match_ids == []:
            match_ids = None
        nodes = Node.objects.get_visible_nodes(request.user, ids=match_ids)
        return nodes.order_by('id')

    @api_exported('acquire', 'POST')
    def acquire(self, request):
        """Acquire an available node for deployment."""
        node = Node.objects.get_available_node_for_acquisition(request.user)
        if node is None:
            raise NodesNotAvailable("No node is available.")
        node.acquire(request.user)
        node.save()
        return node

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodeMacsHandler(BaseHandler):
    """
    Manage all the MAC Addresses linked to a Node / Create a new MAC Address
    for a Node.

    """
    allowed_methods = ('GET', 'POST',)

    def read(self, request, system_id):
        """Read all MAC Addresses related to a Node."""
        node = Node.objects.get_visible_node_or_404(
            user=request.user, system_id=system_id)

        return MACAddress.objects.filter(node=node).order_by('id')

    def create(self, request, system_id):
        """Create a MAC Address for a specified Node."""
        try:
            node = Node.objects.get_visible_node_or_404(
                user=request.user, system_id=system_id)
            mac = node.add_mac_address(request.data.get('mac_address', None))
            return mac
        except ValidationError as e:
            return HttpResponseBadRequest(e.message_dict)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('node_macs_handler', ['system_id'])


class NodeMacHandler(BaseHandler):
    """Manage a MAC Address linked to a Node."""
    allowed_methods = ('GET', 'DELETE')
    fields = ('mac_address',)
    model = MACAddress

    def read(self, request, system_id, mac_address):
        """Read a MAC Address related to a Node."""
        node = Node.objects.get_visible_node_or_404(
            user=request.user, system_id=system_id)

        validate_mac(mac_address)
        return get_object_or_404(
            MACAddress, node=node, mac_address=mac_address)

    def delete(self, request, system_id, mac_address):
        """Delete a specific MAC Address for the specified Node."""
        validate_mac(mac_address)
        node = Node.objects.get_visible_node_or_404(
            user=request.user, system_id=system_id)

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


@api_operations
class FilesHandler(BaseHandler):
    """File management operations."""
    allowed_methods = ('GET', 'POST',)

    @api_exported('get', 'GET')
    def get(self, request):
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

    @api_exported('add', 'POST')
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
class AccountHandler(BaseHandler):
    """Manage the current logged-in user."""
    allowed_methods = ('POST',)

    @api_exported('create_authorisation_token', method='POST')
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

    @api_exported('delete_authorisation_token', method='POST')
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

    @api_exported('set_config', method='POST')
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

    @api_exported('get_config', method='GET')
    def get_config(self, request):
        """Get a config value.

        :param name: The name of the config item to be retrieved.
        :type name: basestring
        """
        name = get_mandatory_param(request.GET, 'name')
        value = Config.objects.get_config(name)
        return HttpResponse(json.dumps(value), content_type='application/json')


def generate_api_doc(add_title=False):
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

    messages = []
    if add_title:
        messages.extend([
            '**********************\n',
            'MAAS API documentation\n',
            '**********************\n',
            '\n\n']
            )
    for doc in docs:
        for method in doc.get_methods():
            messages.append(
                "%s %s\n  %s\n\n" % (
                    method.http_name, doc.resource_uri_template,
                    method.doc))
    return ''.join(messages)


def reST_to_html_fragment(a_str):
    parts = core.publish_parts(source=a_str, writer_name='html')
    return parts['body_pre_docinfo'] + parts['fragment']


_API_DOC = None


def api_doc(request):
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
