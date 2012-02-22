# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'IndexHandler',
    'MetaDataHandler',
    'UserDataHandler',
    'VersionIndexHandler',
    ]

from django.http import HttpResponse
from maasserver.exceptions import (
    MaasAPINotFound,
    PermissionDenied,
    Unauthorized,
    )
from metadataserver.models import NodeKey
from piston.handler import BaseHandler


class UnknownMetadataVersion(MaasAPINotFound):
    """Not a known metadata version."""


class UnknownNode(MaasAPINotFound):
    """Not a known node."""


def extract_oauth_key(auth_data):
    """Extract the oauth key from auth data in HTTP header."""
    for entry in auth_data.split():
        key_value = entry.split('=', 1)
        if len(key_value) == 2:
            key, value = key_value
            if key == 'oauth_token':
                return value.rstrip(',').strip('"')
    raise Unauthorized("No oauth token found for metadata request.")


def get_node_for_request(request):
    """Return the `Node` that `request` is authorized to query for."""
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header is None:
        raise Unauthorized("No authorization header received.")
    key = extract_oauth_key(auth_header)
    try:
        return NodeKey.objects.get_node_for_key(key)
    except NodeKey.DoesNotExist:
        raise PermissionDenied("Not authenticated as a known node.")


def make_text_response(contents):
    """Create a response containing `contents` as plain text."""
    return HttpResponse(contents, mimetype='text/plain')


def make_list_response(items):
    """Create an `HttpResponse` listing `items`, one per line."""
    return make_text_response('\n'.join(items))


def check_version(version):
    """Check that `version` is a supported metadata version."""
    if version != 'latest':
        raise UnknownMetadataVersion("Unknown metadata version: %s" % version)


class MetadataViewHandler(BaseHandler):
    allowed_methods = ('GET',)

    def read(self, request):
        return make_list_response(self.fields)


class IndexHandler(MetadataViewHandler):
    """Top-level metadata listing."""

    fields = ('latest',)


class VersionIndexHandler(MetadataViewHandler):
    """Listing for a given metadata version."""

    fields = ('meta-data', 'user-data')

    def read(self, request, version):
        check_version(version)
        return super(VersionIndexHandler, self).read(request)


class MetaDataHandler(VersionIndexHandler):
    """Meta-data listing for a given version."""

    fields = ('local-hostname',)

    def get_attribute_producer(self, item):
        """Return a callable to deliver a given metadata item.

        :param item: Sub-path for the attribute, e.g. "local-hostname" to
            get a handler that returns the logged-in node's hostname.
        :type item: basestring
        :return: A callable that accepts as arguments the logged-in node;
            the requested metadata version (e.g. "latest"); and `item`.  It
            returns an HttpResponse.
        :rtype: Callable
        """
        field = item.split('/')[0]
        if field not in self.fields:
            raise MaasAPINotFound("Unknown metadata attribute: %s" % field)

        producers = {
            'local-hostname': self.local_hostname,
        }

        return producers[field]

    def read(self, request, version, item=None):
        check_version(version)
        if item is None or len(item) == 0:
            # Requesting the list of attributes, not any particular
            # attribute.
            return super(MetaDataHandler, self).read(request)

        node = get_node_for_request(request)
        producer = self.get_attribute_producer(item)
        return producer(node, version, item)

    def local_hostname(self, node, version, item):
        return make_text_response(node.hostname)


class UserDataHandler(MetadataViewHandler):
    """User-data blob for a given version."""

    def read(self, request, version):
        check_version(version)
        data = b"User data here."
        return HttpResponse(data, mimetype='application/octet-stream')
