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
    "generate_api_doc",
    "NodeHandler",
    "NodeMacsHandler",
    ]

from functools import wraps
import types

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.http import HttpResponseBadRequest
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from docutils import core
from maasserver.forms import NodeWithMACAddressesForm
from maasserver.macaddress import validate_mac
from maasserver.models import (
    MACAddress,
    Node,
    )
from piston.authentication import OAuthAuthentication
from piston.doc import generate_doc
from piston.handler import BaseHandler
from piston.utils import rc


class MaasAPIAuthentication(OAuthAuthentication):
    """A piston authentication class that uses the currently logged-in user
    if there is one, and defaults to piston's OAuthAuthentication if not.

    """

    def is_authenticated(self, request):
        if request.user.is_authenticated():
            return request.user
        else:
            return super(
                MaasAPIAuthentication, self).is_authenticated(request)

    def challenge(self):
        return rc.FORBIDDEN


def validate_and_save(obj):
    try:
        obj.full_clean()
        obj.save()
        return obj
    except ValidationError, e:
        return HttpResponseBadRequest(
            e.message_dict, content_type='application/json')


def validate_mac_address(mac_address):
    try:
        validate_mac(mac_address)
        return True, None
    except ValidationError:
        return False, HttpResponseBadRequest('Invalid MAC Address.')


def perm_denied_handler(view_func):
    def _decorator(request, *args, **kwargs):
        try:
            response = view_func(request, *args, **kwargs)
            return response
        except PermissionDenied:
            return rc.FORBIDDEN
    return wraps(view_func)(_decorator)


dispatch_methods = {
    'GET': 'read',
    'POST': 'create',
    'PUT': 'update',
    'DELETE': 'delete',
    }


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
    for name, value in vars(cls).iteritems():
        overriden_methods.update(getattr(value, '_api_exported', {}))
    # Override the appropriate methods with a 'dispatcher' method.
    for method in overriden_methods:
        operations = {
            name: value for name, value in vars(cls).iteritems()
            if is_api_exported(value, method)}
        cls._available_api_methods = getattr(
            cls, "_available_api_methods", {}).copy()
        cls._available_api_methods[method] = {
            (name if op._api_exported[method] is True
                else op._api_exported[method]): op
            for name, op in operations.iteritems()
            if method in op._api_exported}

        def dispatcher(self, request, *args, **kwargs):
            return perform_api_operation(
                self, request, request.method, *args, **kwargs)

        method_name = str(dispatch_methods[method])
        dispatcher.__name__ = method_name
        dispatcher.__doc__ = (
            "The actual operation to execute depends on the value of the '%s' "
            "parameter:\n\n" % OP_PARAM)
        dispatcher.__doc__ += "\n- ".join(
            "- Operation '%s' (op=%s):\n\t%s" % (name, name, op.__doc__)
            for name, op in cls._available_api_methods[method].iteritems())

        # Add {'create','read','update','delete'} method.
        setattr(cls, method_name, dispatcher)
    return cls


class NodeHandler(BaseHandler):
    """Manage individual Nodes."""
    allowed_methods = ('GET', 'DELETE', 'PUT')
    model = Node
    fields = ('system_id', 'hostname', ('macaddress_set', ('mac_address',)))

    @perm_denied_handler
    def read(self, request, system_id):
        """Read a specific Node."""
        return Node.objects.get_visible_node_or_404(
            system_id=system_id, user=request.user)

    @perm_denied_handler
    def update(self, request, system_id):
        """Update a specific Node."""
        node = Node.objects.get_visible_node_or_404(
            system_id=system_id, user=request.user)
        for key, value in request.data.items():
            setattr(node, key, value)
        return validate_and_save(node)

    @perm_denied_handler
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


@api_operations
class NodesHandler(BaseHandler):
    """Manage collection of Nodes / Create Nodes."""
    allowed_methods = ('GET', 'POST',)

    @api_exported('list', 'GET')
    def list(self, request):
        """Read all Nodes."""
        return Node.objects.get_visible_nodes(request.user).order_by('id')

    @api_exported('new', 'POST')
    def new(self, request):
        """Create a new Node."""
        form = NodeWithMACAddressesForm(request.data)
        if form.is_valid():
            node = form.save()
            return node
        else:
            return HttpResponseBadRequest(
                form.errors, content_type='application/json')

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodeMacsHandler(BaseHandler):
    """
    Manage all the MAC Addresses linked to a Node / Create a new MAC Address
    for a Node.

    """
    allowed_methods = ('GET', 'POST',)

    @perm_denied_handler
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
        except ValidationError, e:
            return HttpResponseBadRequest(e.message_dict)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('node_macs_handler', ['system_id'])


class NodeMacHandler(BaseHandler):
    """Manage a MAC Address linked to a Node."""
    allowed_methods = ('GET', 'DELETE')
    fields = ('mac_address',)
    model = MACAddress

    @perm_denied_handler
    def read(self, request, system_id, mac_address):
        """Read a MAC Address related to a Node."""
        node = Node.objects.get_visible_node_or_404(
            user=request.user, system_id=system_id)

        valid, response = validate_mac_address(mac_address)
        if not valid:
            return response
        return get_object_or_404(
            MACAddress, node=node, mac_address=mac_address)

    @perm_denied_handler
    def delete(self, request, system_id, mac_address):
        """Delete a specific MAC Address for the specified Node."""
        valid, response = validate_mac_address(mac_address)
        if not valid:
            return response

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
class AccountHandler(BaseHandler):
    """Manage the current logged-in user."""
    allowed_methods = ('POST',)

    @api_exported('reset_authorisation_token')
    def reset_authorisation_token(self, request):
        """Regenerate the token and the secret of the OAuth Token.

        :return: A json dict with three keys: 'token_key',
            'token_secret' and 'consumer_key' (e.g.
            {token_key: 's65244576fgqs', token_secret: 'qsdfdhv34',
             consumer_key: '68543fhj854fg'}).

        """
        profile = request.user.get_profile()
        consumer, token = profile.reset_authorisation_token()
        return {
            'token_key': token.key, 'token_secret': token.secret,
            'consumer_key': consumer.key,
            }


def generate_api_doc():
    docs = (
        generate_doc(NodesHandler),
        generate_doc(NodeHandler),
        generate_doc(NodeMacsHandler),
        generate_doc(NodeMacHandler),
        )

    messages = []
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
