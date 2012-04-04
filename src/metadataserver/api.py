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

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from maasserver.api import (
    api_exported,
    api_operations,
    extract_oauth_key,
    get_mandatory_param,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodeStateViolation,
    Unauthorized,
    )
from maasserver.models import (
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    SSHKey,
    )
from metadataserver.models import (
    NodeKey,
    NodeUserData,
    )
from piston.handler import BaseHandler
from piston.utils import rc


class UnknownMetadataVersion(MAASAPINotFound):
    """Not a known metadata version."""


class UnknownNode(MAASAPINotFound):
    """Not a known node."""


def get_node_for_request(request):
    """Return the `Node` that `request` is authorized to query for."""
    auth_header = request.META.get('HTTP_AUTHORIZATION')
    if auth_header is None:
        raise Unauthorized("No authorization header received.")
    key = extract_oauth_key(auth_header)
    if key is None:
        raise Unauthorized("No oauth token found for metadata request.")
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
    if version not in ('latest', '2012-03-01'):
        raise UnknownMetadataVersion("Unknown metadata version: %s" % version)


class MetadataViewHandler(BaseHandler):
    allowed_methods = ('GET',)

    def read(self, request):
        return make_list_response(sorted(self.fields))


class IndexHandler(MetadataViewHandler):
    """Top-level metadata listing."""

    fields = ('latest', '2012-03-01')


@api_operations
class VersionIndexHandler(MetadataViewHandler):
    """Listing for a given metadata version."""
    allowed_methods = ('GET', 'POST')
    fields = ('meta-data', 'user-data')

    # States in which a node is allowed to signal commissioning status.
    # (Only in Commissioning state, however, will it have any effect.)
    signalable_states = [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.READY,
        NODE_STATUS.FAILED_TESTS,
        ]

    # Statuses that a commissioning node may signal, and the respective
    # state transitions that they trigger on the node.
    signaling_statuses = {
        'OK': NODE_STATUS.READY,
        'FAILED': NODE_STATUS.FAILED_TESTS,
        'WORKING': None,
    }

    def read(self, request, version):
        """Read the metadata index for this version."""
        check_version(version)
        if NodeUserData.objects.has_user_data(get_node_for_request(request)):
            shown_fields = self.fields
        else:
            shown_fields = list(self.fields)
            shown_fields.remove('user-data')
        return make_list_response(sorted(shown_fields))

    @api_exported('signal', 'POST')
    def signal(self, request, version=None):
        """Signal commissioning status.

        A commissioning node can call this to report progress of the
        commissioning process to the metadata server.

        Calling this from a node that is not Commissioning, Ready, or
        Failed Tests is an error.  Signaling completion more than once is not
        an error; all but the first successful call are ignored.

        :param status: A commissioning status code.  This can be "OK" (to
            signal that commissioning has completed successfully), or "FAILED"
            (to signal failure), or "WORKING" (for progress reports).
        """
        node = get_node_for_request(request)
        status = request.POST.get('status', None)

        status = get_mandatory_param(request.POST, 'status')
        if node.status not in self.signalable_states:
            raise NodeStateViolation(
                "Node wasn't commissioning (status is %s)"
                % NODE_STATUS_CHOICES_DICT[node.status])

        if status not in self.signaling_statuses:
            raise MAASAPIBadRequest(
                "Unknown commissioning status: '%s'" % status)

        if node.status != NODE_STATUS.COMMISSIONING:
            # Already registered.  Nothing to be done.
            return rc.ALL_OK

        target_status = self.signaling_statuses.get(status)
        if target_status not in (None, node.status):
            node.status = target_status
            node.save()

        return rc.ALL_OK


class MetaDataHandler(VersionIndexHandler):
    """Meta-data listing for a given version."""

    fields = ('instance-id', 'local-hostname', 'public-keys')

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
            raise MAASAPINotFound("Unknown metadata attribute: %s" % field)

        producers = {
            'local-hostname': self.local_hostname,
            'instance-id': self.instance_id,
            'public-keys': self.public_keys,
        }

        return producers[field]

    def read(self, request, version, item=None):
        check_version(version)
        node = get_node_for_request(request)

        # Requesting the list of attributes, not any particular
        # attribute.
        if item is None or len(item) == 0:
            fields = list(self.fields)
            # Add public-keys to the list of attributes, if the
            # node has registered SSH keys.
            keys = SSHKey.objects.get_keys_for_user(user=node.owner)
            if not keys:
                fields.remove('public-keys')
            return make_list_response(sorted(fields))

        producer = self.get_attribute_producer(item)
        return producer(node, version, item)

    def local_hostname(self, node, version, item):
        """Produce local-hostname attribute."""
        return make_text_response(node.hostname)

    def instance_id(self, node, version, item):
        """Produce instance-id attribute."""
        return make_text_response(node.system_id)

    def public_keys(self, node, version, item):
        """ Produce public-keys attribute."""
        keys = SSHKey.objects.get_keys_for_user(user=node.owner)
        if not keys:
            raise MAASAPINotFound("No registered public keys")
        return make_list_response(keys)


class UserDataHandler(MetadataViewHandler):
    """User-data blob for a given version."""

    def read(self, request, version):
        check_version(version)
        node = get_node_for_request(request)
        try:
            return HttpResponse(
                NodeUserData.objects.get_user_data(node),
                mimetype='application/octet-stream')
        except NodeUserData.DoesNotExist:
            raise MAASAPINotFound("No user data available for this node.")
