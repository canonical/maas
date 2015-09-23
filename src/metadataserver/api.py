# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'AnonMetaDataHandler',
    'CommissioningScriptsHandler',
    'CurtinUserDataHandler',
    'IndexHandler',
    'MetaDataHandler',
    'UserDataHandler',
    'VersionIndexHandler',
    ]

import base64
import bz2
import httplib
import json

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from maasserver.api.nodes import store_node_power_parameters
from maasserver.api.support import (
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
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
    Interface,
    Node,
    SSHKey,
    SSLKey,
)
from maasserver.models.event import Event
from maasserver.models.tag import Tag
from maasserver.populate_tags import populate_tags_for_single_node
from maasserver.preseed import (
    get_curtin_userdata,
    get_enlist_preseed,
    get_enlist_userdata,
    get_preseed,
)
from maasserver.utils import find_nodegroup
from maasserver.utils.orm import get_one
from metadataserver import logger
from metadataserver.enum import (
    RESULT_TYPE,
    SIGNAL_STATUS,
)
from metadataserver.fields import Bin
from metadataserver.models import (
    CommissioningScript,
    NodeKey,
    NodeResult,
    NodeUserData,
)
from metadataserver.models.commissioningscript import (
    BUILTIN_COMMISSIONING_SCRIPTS,
)
from metadataserver.user_data import poweroff
from piston.utils import rc
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_TYPES,
)


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
    match = get_one(Interface.objects.filter(mac_address=mac))
    if match is None:
        raise MAASAPINotFound()
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


class MetadataViewHandler(OperationsHandler):
    create = update = delete = None

    def read(self, request, mac=None):
        return make_list_response(sorted(self.fields))


class IndexHandler(MetadataViewHandler):
    """Top-level metadata listing."""

    fields = ('latest', '2012-03-01')


class StatusHandler(MetadataViewHandler):
    read = update = delete = None

    def create(self, request, system_id):
        """Receive and process a status message from a node.

        A node can call this to report progress of its
        commissioning/installation process to the metadata server.

        Calling this from a node that is not Allocated, Commissioning, Ready,
        or Failed Tests will update the substatus_message node attribute.
        Signaling completion more than once is not an error; all but the first
        successful call are ignored.

        This method accepts a single JSON-encoded object payload, described as
        follows.

        {
            "event_type": "finish",
            "origin": "curtin",
            "description": "Finished XYZ",
            "name": "cmd-install",
            "result": "SUCCESS",
            "files": [
                {
                    "name": "logs.tgz",
                    "encoding": "base64",
                    "content": "QXVnIDI1IDA3OjE3OjAxIG1hYXMtZGV2...
                },
                {
                    "name": "results.log",
                    "compression": "bzip2"
                    "encoding": "base64",
                    "content": "AAAAAAAAAAAAAAAAAAAAAAA...
                }
            ]
        }

        `event_type` can be "start", "progress" or "finish".

        `origin` tells us the program that originated the call.

        `description` is a human-readable, operator-friendly string that
        conveys what is being done to the node and that can be presented on the
        web UI.

        `name` is the name of the activity that's being executed. It's
        meaningful to the calling program and is a slash-separated path. We are
        mainly concerned with top-level events (no slashes), which are used to
        change the status of the node.

        `result` can be "SUCCESS" or "FAILURE" indicating whether the activity
        was successful or not.

        `files`, when present, contains one or more files. The attribute `path`
        tells us the name of the file, `compression` tells the compression we
        used before applying the `encoding` and content is the encoded data
        from the file. If the file being sent is the result of the execution of
        a script, the `result` key will hold its value. If `result` is not
        sent, it is interpreted as zero.

        """

        def _add_event_to_node_event_log(node, origin, description):
            """Add an entry to the node's event log."""
            if node.status == NODE_STATUS.COMMISSIONING:
                type_name = EVENT_TYPES.NODE_COMMISSIONING_EVENT
            elif node.status == NODE_STATUS.DEPLOYING:
                type_name = EVENT_TYPES.NODE_INSTALL_EVENT
            else:
                type_name = EVENT_TYPES.NODE_STATUS_EVENT

            event_details = EVENT_DETAILS[type_name]
            return Event.objects.register_event_and_event_type(
                node.system_id, type_name, type_level=event_details.level,
                type_description=event_details.description,
                event_description="'%s' %s" % (origin, description))

        def _retrieve_content(compression, encoding, content):
            """Extract the content of the sent file."""
            # Select the appropriate decompressor.
            if compression is None:
                decompress = lambda s: s
            elif compression == 'bzip2':
                decompress = bz2.decompress
            else:
                raise MAASAPIBadRequest(
                    'Invalid compression: %s' % sent_file['compression'])

            # Select the appropriate decoder.
            if encoding == 'base64':
                decode = base64.decodestring
            else:
                raise MAASAPIBadRequest(
                    'Invalid encoding: %s' % sent_file['encoding'])

            return decompress(decode(sent_file['content']))

        def _save_commissioning_result(node, path, exit_status, content):
            # Depending on the name of the file received, we need to invoke a
            # function to process it.
            if sent_file['path'] in BUILTIN_COMMISSIONING_SCRIPTS:
                postprocess_hook = BUILTIN_COMMISSIONING_SCRIPTS[path]['hook']
                postprocess_hook(
                    node=node, output=content, exit_status=exit_status)
            return NodeResult.objects.store_data(
                node, path, script_result=exit_status,
                result_type=RESULT_TYPE.COMMISSIONING, data=Bin(content))

        def _save_installation_result(node, path, content):
            return NodeResult.objects.store_data(
                node, path, script_result=0,
                result_type=RESULT_TYPE.INSTALLATION, data=Bin(content))

        def _is_top_level(activity_name):
            """Top-level events do not have slashes in theit names."""
            return '/' not in activity_name

        node = get_queried_node(request)
        payload = request.read()
        try:
            message = json.loads(payload)
        except ValueError:
            message = "Status payload is not valid JSON:\n%s\n\n" % payload
            logger.error(message)
            raise MAASAPIBadRequest(message)

        # Mandatory attributes.
        try:
            event_type = message['event_type']
            origin = message['origin']
            activity_name = message['name']
            description = message['description']
        except KeyError:
            message = 'Missing parameter in status message %s' % payload
            logger.error(message)
            raise MAASAPIBadRequest(message)

        # Optional attributes.
        result = message.get('result')

        # Add this event to the node event log.
        _add_event_to_node_event_log(node, origin, description)

        # Save attached files, if any.
        for sent_file in message.get('files', []):

            content = _retrieve_content(
                compression=sent_file.get('compression'),
                encoding=sent_file['encoding'],
                content=sent_file['content'])

            # Set the result type according to the node's status.
            if node.status == NODE_STATUS.COMMISSIONING:
                _save_commissioning_result(
                    node, sent_file['path'], sent_file.get('result', 0),
                    content)
            elif node.status == NODE_STATUS.DEPLOYING:
                _save_installation_result(node, sent_file['path'], content)
            else:
                raise MAASAPIBadRequest(
                    "Invalid status for saving files: %d" % node.status)

        # At the end of a top-level event, we change the node status.
        if _is_top_level(activity_name) and event_type == 'finish':
            if node.status == NODE_STATUS.COMMISSIONING:

                # Ensure that any IP lease are forcefully released in case
                # the host didn't bother doing that.
                node.release_leases()

                node.stop_transition_monitor()
                if result == 'SUCCESS':
                    # Recalculate tags.
                    populate_tags_for_single_node(Tag.objects.all(), node)

                    # Setup the default storage layout and the initial
                    # networking configuration for the node.
                    node.set_default_storage_layout()
                    node.set_initial_networking_configuration()
                elif result in ['FAIL', 'FAILURE']:
                    node.status = NODE_STATUS.FAILED_COMMISSIONING

            elif node.status == NODE_STATUS.DEPLOYING:
                if result in ['FAIL', 'FAILURE']:
                    node.mark_failed(
                        None,
                        "Installation failed (refer to the "
                        "installation log for more information).")
            elif node.status == NODE_STATUS.DISK_ERASING:
                if result == 'SUCCESS':
                    # disk erasing complete, release node.
                    node.release()
                elif result in ['FAIL', 'FAILURE']:
                    node.mark_failed(None, "Failed to erase disks.")

            # Deallocate the node if we enter any terminal state.
            if node.status in [
                    NODE_STATUS.READY,
                    NODE_STATUS.FAILED_COMMISSIONING,
                    NODE_STATUS.FAILED_DISK_ERASING]:
                node.owner = None
                node.error = 'failed: %s' % description

        node.save()
        return rc.ALL_OK


class VersionIndexHandler(MetadataViewHandler):
    """Listing for a given metadata version."""
    create = update = delete = None
    fields = ('maas-commissioning-scripts', 'meta-data', 'user-data')

    # States in which a node is allowed to signal
    # commissioning/installing status.
    # (Only in Commissioning/Deploying state, however,
    # will it have any effect.)
    signalable_states = [
        NODE_STATUS.BROKEN,
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.READY,
        NODE_STATUS.DISK_ERASING,
        ]

    effective_signalable_states = [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DISK_ERASING,
    ]

    # Statuses that a commissioning node may signal, and the respective
    # state transitions that they trigger on the node.
    signaling_statuses = {
        SIGNAL_STATUS.OK: NODE_STATUS.READY,
        SIGNAL_STATUS.FAILED: NODE_STATUS.FAILED_COMMISSIONING,
        SIGNAL_STATUS.WORKING: None,
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

    def _store_installation_results(self, node, request):
        """Store installation result file for `node`."""
        for name, uploaded_file in request.FILES.items():
            raw_content = uploaded_file.read()
            NodeResult.objects.store_data(
                node, name, script_result=0,
                result_type=RESULT_TYPE.INSTALLATION, data=Bin(raw_content))

    def _store_commissioning_results(self, node, request):
        """Store commissioning result files for `node`."""
        script_result = int(request.POST.get('script_result', 0))
        for name, uploaded_file in request.FILES.items():
            raw_content = uploaded_file.read()
            if name in BUILTIN_COMMISSIONING_SCRIPTS:
                postprocess_hook = BUILTIN_COMMISSIONING_SCRIPTS[name]['hook']
                postprocess_hook(
                    node=node, output=raw_content,
                    exit_status=script_result)
            NodeResult.objects.store_data(
                node, name, script_result,
                result_type=RESULT_TYPE.COMMISSIONING, data=Bin(raw_content))

    @operation(idempotent=False)
    def signal(self, request, version=None, mac=None):
        """Signal commissioning/installation status.

        A commissioning/installing node can call this to report progress of
        the commissioning/installation process to the metadata server.

        Calling this from a node that is not Allocated, Commissioning, Ready,
        or Failed Tests is an error. Signaling completion more than once is
        not an error; all but the first successful call are ignored.

        :param status: A commissioning/installation status code. This can be
            "OK" (to signal that commissioning/installation has completed
            successfully), or "FAILED" (to signal failure), or "WORKING" (for
            progress reports).
        :param script_result: If this call uploads files, this parameter must
            be provided and will be stored as the return value for the script
            which produced these files.
        :param error: An optional error string. If given, this will be stored
            (overwriting any previous error string), and displayed in the MAAS
            UI. If not given, any previous error string will be cleared.
        """
        node = get_queried_node(request, for_mac=mac)
        status = get_mandatory_param(request.POST, 'status')
        if node.status not in self.signalable_states:
            raise NodeStateViolation(
                "Node wasn't commissioning/installing (status is %s)"
                % NODE_STATUS_CHOICES_DICT[node.status])

        # These statuses are acceptable for commissioning, disk erasing,
        # and deploying.
        if status not in self.signaling_statuses:
            raise MAASAPIBadRequest(
                "Unknown commissioning/installation status: '%s'" % status)

        if node.status not in self.effective_signalable_states:
            # If commissioning, it is already registered.  Nothing to be done.
            # If it is installing, should be in deploying state.
            return rc.ALL_OK

        if node.status == NODE_STATUS.COMMISSIONING:
            # Ensure that any IP lease are forcefully released in case
            # the host didn't bother doing that.
            if status != SIGNAL_STATUS.WORKING:
                node.release_leases()

            # Store the commissioning results.
            self._store_commissioning_results(node, request)

            # Commissioning was successful setup the default storage layout
            # and the initial networking configuration for the node.
            if status == SIGNAL_STATUS.OK:
                node.set_default_storage_layout()
                node.set_initial_networking_configuration()

            # XXX 2014-10-21 newell, bug=1382075
            # Auto detection for IPMI tries to save power parameters
            # for Moonshot.  This causes issues if the node's power type
            # is already MSCM as it uses SSH instead of IPMI.  This fix
            # is temporary as power parameters should not be overwritten
            # during commissioning because MAAS already has knowledge to
            # boot the node.
            # See MP discussion bug=1389808, for further details on why
            # we are using bug fix 1382075 here.
            if node.power_type != "mscm":
                store_node_power_parameters(node, request)
            node.stop_transition_monitor()
            target_status = self.signaling_statuses.get(status)

            # Recalculate tags when commissioning ends.
            if target_status == NODE_STATUS.READY:
                populate_tags_for_single_node(Tag.objects.all(), node)

        elif node.status == NODE_STATUS.DEPLOYING:
            self._store_installation_results(node, request)
            if status == SIGNAL_STATUS.FAILED:
                node.mark_failed(
                    None,
                    "Installation failed (refer to the "
                    "installation log for more information).")
            target_status = None
        elif node.status == NODE_STATUS.DISK_ERASING:
            if status == SIGNAL_STATUS.OK:
                # disk erasing complete, release node
                node.release()
            elif status == SIGNAL_STATUS.FAILED:
                node.mark_failed(None, "Failed to erase disks.")
            target_status = None

        if target_status in (None, node.status):
            # No status change.  Nothing to be done.
            return rc.ALL_OK

        node.status = target_status
        # When moving to a terminal state, remove the allocation.
        node.owner = None
        node.error = request.POST.get('error', '')

        # Done.
        node.save()
        return rc.ALL_OK

    @operation(idempotent=False)
    def netboot_off(self, request, version=None, mac=None):
        """Turn off netboot on the node.

        A deploying node can call this to turn off netbooting when
        it finishes installing itself.
        """
        node = get_queried_node(request, for_mac=mac)
        node.set_netboot(False)
        return rc.ALL_OK

    @operation(idempotent=False)
    def netboot_on(self, request, version=None, mac=None):
        """Turn on netboot on the node."""
        node = get_queried_node(request, for_mac=mac)
        node.set_netboot(True)
        return rc.ALL_OK


class MetaDataHandler(VersionIndexHandler):
    """Meta-data listing for a given version."""

    fields = ('instance-id', 'local-hostname', 'public-keys', 'x509')

    def get_attribute_producer(self, item):
        """Return a callable to deliver a given metadata item.

        :param item: Sub-path for the attribute, e.g. "local-hostname" to
            get a handler that returns the logged-in node's hostname.
        :type item: unicode
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
            'x509': self.ssl_certs,
        }

        return producers[field]

    def read(self, request, version, mac=None, item=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)

        # Requesting the list of attributes, not any particular
        # attribute.
        if item is None or len(item) == 0:
            fields = list(self.fields)
            commissioning_without_ssh = (
                node.status == NODE_STATUS.COMMISSIONING and
                not node.enable_ssh)
            # Add public-keys to the list of attributes, if the
            # node has registered SSH keys.
            keys = SSHKey.objects.get_keys_for_user(user=node.owner)
            if not keys or commissioning_without_ssh:
                fields.remove('public-keys')
            return make_list_response(sorted(fields))

        producer = self.get_attribute_producer(item)
        return producer(node, version, item)

    def local_hostname(self, node, version, item):
        """Produce local-hostname attribute."""
        return make_text_response(node.fqdn)

    def instance_id(self, node, version, item):
        """Produce instance-id attribute."""
        return make_text_response(node.system_id)

    def public_keys(self, node, version, item):
        """ Produce public-keys attribute."""
        return make_list_response(
            SSHKey.objects.get_keys_for_user(user=node.owner))

    def ssl_certs(self, node, version, item):
        """ Produce x509 certs attribute. """
        return make_list_response(
            SSLKey.objects.get_keys_for_user(user=node.owner))


class UserDataHandler(MetadataViewHandler):
    """User-data blob for a given version."""

    def read(self, request, version, mac=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        try:
            # When a node is deploying, cloud-init's request
            # for user-data is when MAAS hands the node
            # off to a user.
            if node.status == NODE_STATUS.DEPLOYING:
                node.end_deployment()
            # If this node is supposed to be powered off, serve the
            # 'poweroff' userdata.
            if node.get_boot_purpose() == 'poweroff':
                user_data = poweroff.generate_user_data(node=node)
            else:
                user_data = NodeUserData.objects.get_user_data(node)
            return HttpResponse(
                user_data, mimetype='application/octet-stream')
        except NodeUserData.DoesNotExist:
            logger.info(
                "No user data registered for node named %s" % node.hostname)
            return HttpResponse(status=httplib.NOT_FOUND)


class CurtinUserDataHandler(MetadataViewHandler):
    """Curtin user-data blob for a given version."""

    def read(self, request, version, mac=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        user_data = get_curtin_userdata(node)
        return HttpResponse(
            user_data,
            mimetype='application/octet-stream')


class CommissioningScriptsHandler(MetadataViewHandler):
    """Return a tar archive containing the commissioning scripts."""

    def read(self, request, version, mac=None):
        check_version(version)
        return HttpResponse(
            CommissioningScript.objects.get_archive(),
            mimetype='application/tar')


class EnlistMetaDataHandler(OperationsHandler):
    """this has to handle the 'meta-data' portion of the meta-data api
    for enlistment only.  It should mimic the read-only portion
    of /VersionIndexHandler"""

    create = update = delete = None

    data = {
        'instance-id': 'i-maas-enlistment',
        'local-hostname': "maas-enlisting-node",
        'public-keys': "",
    }

    def read(self, request, version, item=None):
        check_version(version)

        # Requesting the list of attributes, not any particular attribute.
        if item is None or len(item) == 0:
            keys = sorted(self.data.keys())
            # There's nothing in public-keys, so we don't advertise it.
            # But cloud-init does ask for it and it's not worth logging
            # a traceback for.
            keys.remove('public-keys')
            return make_list_response(keys)

        if item not in self.data:
            raise MAASAPINotFound("Unknown metadata attribute: %s" % item)

        return make_text_response(self.data[item])


class EnlistUserDataHandler(OperationsHandler):
    """User-data for the enlistment environment"""

    def read(self, request, version):
        check_version(version)
        nodegroup = find_nodegroup(request)
        return HttpResponse(
            get_enlist_userdata(nodegroup=nodegroup), mimetype="text/plain")


class EnlistVersionIndexHandler(OperationsHandler):
    create = update = delete = None
    fields = ('meta-data', 'user-data')

    def read(self, request, version):
        return make_list_response(sorted(self.fields))


class AnonMetaDataHandler(VersionIndexHandler):
    """Anonymous metadata."""

    @operation(idempotent=True)
    def get_enlist_preseed(self, request, version=None):
        """Render and return a preseed script for enlistment."""
        nodegroup = find_nodegroup(request)
        return HttpResponse(
            get_enlist_preseed(nodegroup=nodegroup), mimetype="text/plain")

    @operation(idempotent=True)
    def get_preseed(self, request, version=None, system_id=None):
        """Render and return a preseed script for the given node."""
        node = get_object_or_404(Node, system_id=system_id)
        return HttpResponse(get_preseed(node), mimetype="text/plain")

    @operation(idempotent=False)
    def netboot_off(self, request, version=None, system_id=None):
        """Turn off netboot on the node.

        A commissioning node can call this to turn off netbooting when
        it finishes installing itself.
        """
        node = get_object_or_404(Node, system_id=system_id)
        node.set_netboot(False)

        # Build and register an event for "node installation finished".
        # This is a best-guess. At the moment, netboot_off() only gets
        # called when the node has finished installing, so it's an
        # accurate predictor of the end of the install process.
        type_name = EVENT_TYPES.NODE_INSTALLATION_FINISHED
        event_details = EVENT_DETAILS[type_name]
        Event.objects.register_event_and_event_type(
            node.system_id, type_name, type_level=event_details.level,
            type_description=event_details.description,
            event_description="Node disabled netboot")
        return rc.ALL_OK
