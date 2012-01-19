# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import print_function

"""API."""

__metaclass__ = type
__all__ = [
    "NodeHandler",
    "NodeMacsHandler",
    ]

from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404
from maasserver.macaddress import validate_mac
from maasserver.models import (
    MACAddress,
    Node,
    )
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
    allowed_methods = ('GET', 'POST', 'DELETE', 'PUT')
    model = Node
    fields = ('system_id', 'hostname', ('macaddress_set', ('mac_address',)))

    def read(self, request, system_id=None):
        if system_id is not None:
            return get_object_or_404(Node, system_id=system_id)
        else:
            return Node.objects.all().order_by('id')

    def create(self, request):
        if 'status' in request.data:
            return bad_request('Cannot set the status for a node.')

        node = Node(status='NEW', **dict(request.data.items()))
        return validate_and_save(node)

    def update(self, request, system_id):
        node = get_object_or_404(Node, system_id=system_id)
        for key, value in request.data.items():
            setattr(node, key, value)
        return validate_and_save(node)

    def delete(self, request, system_id):
        node = get_object_or_404(Node, system_id=system_id)
        node.delete()
        return rc.DELETED


class NodeMacsHandler(BaseHandler):
    allowed_methods = ('GET', 'POST', 'DELETE')
    fields = ('mac_address',)

    def read(self, request, system_id, mac_address=None):
        node = get_object_or_404(Node, system_id=system_id)
        if mac_address is not None:
            valid, response = validate_mac_address(mac_address)
            if not valid:
                return response
            return get_object_or_404(
                MACAddress, node=node, mac_address=mac_address)
        else:
            return MACAddress.objects.filter(node=node).order_by('id')

    def create(self, request, system_id):
        node = get_object_or_404(Node, system_id=system_id)
        try:
            mac = node.add_mac_address(request.data.get('mac_address', None))
            return mac
        except ValidationError, e:
            return bad_request(format_error_message(e))

    def delete(self, request, system_id, mac_address):
        valid, response = validate_mac_address(mac_address)
        if not valid:
            return response

        node = get_object_or_404(Node, system_id=system_id)
        mac = get_object_or_404(MACAddress, node=node, mac_address=mac_address)
        mac.delete()
        return rc.DELETED
