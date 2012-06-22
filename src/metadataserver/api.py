# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'AnonMetaDataHandler',
    'IndexHandler',
    'MetaDataHandler',
    'UserDataHandler',
    'VersionIndexHandler',
    ]

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api import (
    api_exported,
    api_operations,
    extract_oauth_key,
    get_mandatory_param,
    )
from maasserver.enum import (
    NODE_STATUS,
    NODE_STATUS_CHOICES_DICT,
    )
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodeStateViolation,
    )
from maasserver.models import (
    MACAddress,
    Node,
    SSHKey,
    )
from maasserver.preseed import (
    get_enlist_preseed,
    get_preseed,
    )
from metadataserver.models import (
    NodeCommissionResult,
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
    """Return the `Node` that `request` queries metadata for.

    For this form of access, a node can only query its own metadata.  Thus
    the oauth key used to authenticate the request must belong to the same
    node that is being queried.  Any request that is not made by an
    authenticated node will be denied.
    """
    key = extract_oauth_key(request)
    try:
        return NodeKey.objects.get_node_for_key(key)
    except NodeKey.DoesNotExist:
        raise PermissionDenied("Not authenticated as a known node.")


def get_node_for_mac(mac):
    """Identify node being queried based on its MAC address.

    This form of access is a security hazard, and thus it is permitted only
    on development systems where ALLOW_UNSAFE_METADATA_ACCESS is enabled.
    """
    if not settings.ALLOW_UNSAFE_METADATA_ACCESS:
        raise PermissionDenied(
            "Unauthenticated metadata access is not allowed on this MAAS.")
    matching_macs = list(MACAddress.objects.filter(mac_address=mac))
    if len(matching_macs) == 0:
        raise MAASAPINotFound()
    [match] = matching_macs
    return match.node


def get_queried_node(request, for_mac=None):
    """Identify and authorize the node whose metadata is being queried.

    :param request: HTTP request.  In normal usage, this is authenticated
        with an oauth key; the key maps to the querying node, and the
        querying node always queries itself.
    :param for_mac: Optional MAC address for the node being queried.  If
        this is given, and anonymous metadata access is enabled (do in
        development environments only!) then the node is looked up by its
        MAC address.
    :return: The :class:`Node` whose metadata is being queried.
    """
    if for_mac is None:
        # Identify node, and authorize access, by oauth key.
        return get_node_for_request(request)
    else:
        # Access keyed by MAC address.
        return get_node_for_mac(for_mac)


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

    def read(self, request, mac=None):
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

    def read(self, request, version, mac=None):
        """Read the metadata index for this version."""
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        if NodeUserData.objects.has_user_data(node):
            shown_fields = self.fields
        else:
            shown_fields = list(self.fields)
            shown_fields.remove('user-data')
        return make_list_response(sorted(shown_fields))

    def _store_commissioning_results(self, node, request):
        """Store commissioning result files for `node`."""
        for name, uploaded_file in request.FILES.items():
            contents = uploaded_file.read().decode('utf-8')
            NodeCommissionResult.objects.store_data(node, name, contents)

    @api_exported('POST')
    def signal(self, request, version=None, mac=None):
        """Signal commissioning status.

        A commissioning node can call this to report progress of the
        commissioning process to the metadata server.

        Calling this from a node that is not Commissioning, Ready, or
        Failed Tests is an error.  Signaling completion more than once is not
        an error; all but the first successful call are ignored.

        :param status: A commissioning status code.  This can be "OK" (to
            signal that commissioning has completed successfully), or "FAILED"
            (to signal failure), or "WORKING" (for progress reports).
        :param error: An optional error string.  If given, this will be stored
            (overwriting any previous error string), and displayed in the MAAS
            UI.  If not given, any previous error string will be cleared.
        """
        node = get_queried_node(request, for_mac=mac)
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

        self._store_commissioning_results(node, request)

        target_status = self.signaling_statuses.get(status)
        if target_status in (None, node.status):
            # No status change.  Nothing to be done.
            return rc.ALL_OK

        node.status = target_status
        # When moving to a terminal state, remove the allocation.
        if target_status is not None:
            node.owner = None
        node.error = request.POST.get('error', '')
        node.save()

        return rc.ALL_OK

    @api_exported('POST')
    def netboot_off(self, request, version=None, mac=None):
        """Turn off netboot on the node.

        A commissioning node can call this to turn off netbooting when
        it finishes installing itself.
        """
        node = get_queried_node(request, for_mac=mac)
        node.netboot = False
        node.save()
        return rc.ALL_OK

    @api_exported('POST')
    def netboot_on(self, request, version=None, mac=None):
        """Turn on netboot on the node."""
        node = get_queried_node(request, for_mac=mac)
        node.netboot = True
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

    def read(self, request, version, mac=None, item=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)

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

    def read(self, request, version, mac=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        try:
            return HttpResponse(
                NodeUserData.objects.get_user_data(node),
                mimetype='application/octet-stream')
        except NodeUserData.DoesNotExist:
            raise MAASAPINotFound("No user data available for this node.")


@api_operations
class AnonMetaDataHandler(VersionIndexHandler):
    """Anonymous metadata."""

    @api_exported('GET')
    def get_enlist_preseed(self, request, version=None):
        """Render and return a preseed script for enlistment."""
        return HttpResponse(get_enlist_preseed(), mimetype="text/plain")

    @api_exported('GET')
    def get_preseed(self, request, version=None, system_id=None):
        """Render and return a preseed script for the given node."""
        node = get_object_or_404(Node, system_id=system_id)
        return HttpResponse(get_preseed(node), mimetype="text/plain")

    @api_exported('POST')
    def netboot_off(self, request, version=None, system_id=None):
        """Turn off netboot on the node.

        A commissioning node can call this to turn off netbooting when
        it finishes installing itself.
        """
        node = get_object_or_404(Node, system_id=system_id)
        node.netboot = False
        node.save()
        return rc.ALL_OK
