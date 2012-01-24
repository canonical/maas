# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    "NodeHandler",
    "NodeMacsHandler",
    ]

from functools import wraps

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
    )
from django.shortcuts import (
    get_object_or_404,
    render_to_response,
    )
from django.template import RequestContext
from maasserver.macaddress import validate_mac
from maasserver.models import (
    MACAddress,
    Node,
    )
from piston.doc import generate_doc
from piston.handler import BaseHandler
from piston.utils import rc


def bad_request(message):
    resp = rc.BAD_REQUEST
    resp.write(': %s' % message)
    return resp


def format_error_message(error):
    messages = []
    for k, v in error.message_dict.iteritems():
        if isinstance(v, list):
            messages.append("%s: %s" % (k, "".join(v)))
        else:
            messages.append("%s: %s" % (k, v))
    return "Invalid input: " + " / ".join(messages)


def validate_and_save(obj):
    try:
        obj.full_clean()
        obj.save()
        return obj
    except ValidationError, e:
        return bad_request(format_error_message(e))


def validate_mac_address(mac_address):
    try:
        validate_mac(mac_address)
        return True, None
    except ValidationError:
        return False, bad_request('Invalid MAC Address.')


def perm_denied_handler(view_func):
    def _decorator(request, *args, **kwargs):
        try:
            response = view_func(request, *args, **kwargs)
            return response
        except PermissionDenied:
            return rc.FORBIDDEN
    return wraps(view_func)(_decorator)


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
    def resource_uri(cls, *args, **kwargs):
        return ('node_handler', ['system_id'])


class NodesHandler(BaseHandler):
    """Manage collection of Nodes / Create Nodes."""
    allowed_methods = ('GET', 'POST',)
    model = Node
    fields = ('system_id', 'hostname', ('macaddress_set', ('mac_address',)))

    def read(self, request):
        """Read all Nodes."""
        return Node.objects.get_visible_nodes(request.user).order_by('id')

    def create(self, request):
        """Create a new Node."""
        if 'status' in request.data:
            return bad_request('Cannot set the status for a node.')

        node = Node(**dict(request.data.items()))
        return validate_and_save(node)

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('nodes_handler', [])


class NodeMacsHandler(BaseHandler):
    """
    Manage all the MAC Addresses linked to a Node / Create a new MAC Address
    for a Node.

    """
    allowed_methods = ('GET', 'POST',)
    fields = ('mac_address',)
    model = MACAddress

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
            return bad_request(format_error_message(e))

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
    def resource_uri(cls, *args, **kwargs):
        return ('node_mac_handler', ['system_id', 'mac_address'])


docs = (
    generate_doc(NodesHandler),
    generate_doc(NodeHandler),
    generate_doc(NodeMacsHandler),
    generate_doc(NodeMacHandler),
    )


def api_doc(request):
    return render_to_response(
        'maasserver/api_doc.html', {'docs': docs},
        context_instance=RequestContext(request))
