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

from django.core.exceptions import ValidationError
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


class NodeHandler(BaseHandler):
    """Manage individual Nodes."""
    allowed_methods = ('GET', 'DELETE', 'PUT')
    model = Node
    fields = ('system_id', 'hostname', ('macaddress_set', ('mac_address',)))

    def read(self, request, system_id):
        """Read a specific Node."""
        return get_object_or_404(Node, system_id=system_id)

    def update(self, request, system_id):
        """Update a specific Node."""
        node = get_object_or_404(Node, system_id=system_id)
        for key, value in request.data.items():
            setattr(node, key, value)
        return validate_and_save(node)

    def delete(self, request, system_id):
        """Delete a specific Node."""
        node = get_object_or_404(Node, system_id=system_id)
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
        return Node.objects.all().order_by('id')

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

    def read(self, request, system_id):
        """Read all MAC Addresses related to a Node."""
        node = get_object_or_404(Node, system_id=system_id)
        return MACAddress.objects.filter(node=node).order_by('id')

    def create(self, request, system_id):
        """Create a MAC Address for a specified Node."""
        node = get_object_or_404(Node, system_id=system_id)
        try:
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

    def read(self, request, system_id, mac_address):
        """Read a MAC Address related to a Node."""
        node = get_object_or_404(Node, system_id=system_id)
        valid, response = validate_mac_address(mac_address)
        if not valid:
            return response
        return get_object_or_404(
            MACAddress, node=node, mac_address=mac_address)

    def delete(self, request, system_id, mac_address):
        """Delete a specific MAC Address for the specified Node."""
        valid, response = validate_mac_address(mac_address)
        if not valid:
            return response

        node = get_object_or_404(Node, system_id=system_id)
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
