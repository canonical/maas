# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'metadata_index',
    'meta_data',
    'version_index',
    'user_data',
    ]

from django.http import HttpResponse
from maasserver.exceptions import (
    MaasAPINotFound,
    Unauthorized,
    )
from metadataserver.models import NodeKey


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
                return value
    raise Unauthorized("No oauth token found for metadata request.")


def get_node_for_request(request):
    """Return the `Node` that `request` is authorized to query for."""
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header is None:
        raise Unauthorized("No authorization header received.")
    key = extract_oauth_key(auth_header)
    return NodeKey.objects.get_node_for_key(key)


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


def metadata_index(request):
    """View: top-level metadata listing."""
    return make_list_response(['latest'])


def version_index(request, version):
    """View: listing for a given metadata version."""
    check_version(version)
    return make_list_response(['meta-data', 'user-data'])


def retrieve_unknown_item(node, item_path):
    """Retrieve meta-data: unknown sub-item."""
    raise MaasAPINotFound("No such metadata item: %s" % '/'.join(item_path))


def retrieve_local_hostname(node, item_path):
    """Retrieve meta-data: local-hostname."""
    return make_text_response(node.hostname)


def meta_data(request, version, item=None):
    """View: meta-data listing for a given version, or meta-data item."""
    check_version(version)
    node = get_node_for_request(request)

    # Functions to retrieve meta-data items.
    retrievers = {
        'local-hostname': retrieve_local_hostname,
        }

    if not item:
        return make_list_response(sorted(retrievers.keys()))

    item_path = item.split('/')
    retriever = retrievers.get(item_path[0], retrieve_unknown_item)
    return retriever(node, item_path[1:])


def user_data(request, version):
    """View: user-data blob for a given version."""
    check_version(version)
    data = b"User data here."
    return HttpResponse(data, mimetype='application/octet-stream')
