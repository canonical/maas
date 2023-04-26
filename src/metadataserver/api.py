# Copyright 2012-2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API."""

__all__ = [
    "AnonMetaDataHandler",
    "CommissioningScriptsHandler",
    "CurtinUserDataHandler",
    "IndexHandler",
    "MAASScriptsHandler",
    "MetaDataHandler",
    "NETPLAN_TAR_PATH",
    "UserDataHandler",
    "VersionIndexHandler",
]

import base64
from datetime import datetime
from functools import partial
import http.client
from io import BytesIO
import json
from operator import itemgetter
import os
import tarfile
import time

from django.conf import settings
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from formencode.validators import Int, Number, String
from piston3.utils import rc
import yaml

from maasserver.api.support import (
    AnonymousOperationsHandler,
    operation,
    OperationsHandler,
)
from maasserver.api.utils import (
    extract_oauth_key,
    get_mandatory_param,
    get_optional_param,
)
from maasserver.clusterrpc.driver_parameters import get_driver_types
from maasserver.compose_preseed import get_apt_proxy
from maasserver.enum import NODE_STATUS, NODE_STATUS_CHOICES_DICT, NODE_TYPE
from maasserver.exceptions import (
    ClusterUnavailable,
    MAASAPIBadRequest,
    MAASAPINotFound,
    NodeStateViolation,
)
from maasserver.forms.parameters import ParametersForm
from maasserver.models import (
    Config,
    Interface,
    Node,
    NodeKey,
    NodeMetadata,
    NodeUserData,
    SSHKey,
    SSLKey,
)
from maasserver.models.event import Event
from maasserver.models.tag import Tag
from maasserver.models.timestampedmodel import now
from maasserver.node_status import (
    FAILED_STATUSES,
    NODE_TESTING_RESET_READY_TRANSITIONS,
)
from maasserver.populate_tags import populate_tags_for_single_node
from maasserver.preseed import (
    get_curtin_userdata,
    get_enlist_preseed,
    get_network_yaml_settings,
    get_preseed,
)
from maasserver.preseed_network import NodeNetworkConfiguration
from maasserver.utils import find_rack_controller
from maasserver.utils.orm import get_one, is_retryable_failure
from metadataserver import logger
from metadataserver.enum import (
    SCRIPT_STATUS,
    SCRIPT_STATUS_RUNNING_OR_PENDING,
    SCRIPT_TYPE,
    SIGNAL_STATUS,
    SIGNAL_STATUS_CHOICES,
)
from metadataserver.models import Script, ScriptResult, ScriptSet
from metadataserver.user_data import (
    generate_user_data_for_poweroff,
    generate_user_data_for_status,
)
from metadataserver.vendor_data import get_vendor_data
from provisioningserver.drivers.power import UNKNOWN_POWER_TYPE
from provisioningserver.events import (
    EVENT_DETAILS,
    EVENT_STATUS_MESSAGES,
    EVENT_TYPES,
)
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


# Where the netplan configuration file should be stored in the Scripts tar.
# ../ is added to keep config outside of the scripts directory.
NETPLAN_TAR_PATH = "../config/netplan.yaml"


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
            "Unauthenticated metadata access is not allowed on this MAAS."
        )
    match = get_one(
        Interface.objects.prefetch_related("node_config__node").filter(
            mac_address=mac
        )
    )
    if match is None:
        raise MAASAPINotFound()
    return match.node_config.node


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
    # XXX: Set a charset for text/plain. Django automatically encodes
    # non-binary content using DEFAULT_CHARSET (which is UTF-8 by default) but
    # only sets the charset parameter in the content-type header when a
    # content-type is NOT provided.
    return HttpResponse(contents, content_type="text/plain")


def make_list_response(items):
    """Create an `HttpResponse` listing `items`, one per line."""
    return make_text_response("\n".join(items))


def check_version(version):
    """Check that `version` is a supported metadata version."""
    if version not in ("latest", "2012-03-01"):
        raise UnknownMetadataVersion("Unknown metadata version: %s" % version)


def add_event_to_node_event_log(
    node, origin, action, description, event_type, result=None, created=None
):
    """Add an entry to the node's event log."""
    if node.status == NODE_STATUS.COMMISSIONING:
        if result in ["SUCCESS", None]:
            type_name = EVENT_TYPES.NODE_COMMISSIONING_EVENT
        else:
            type_name = EVENT_TYPES.NODE_COMMISSIONING_EVENT_FAILED
    elif node.status == NODE_STATUS.DEPLOYING:
        if result in ["SUCCESS", None]:
            type_name = EVENT_TYPES.NODE_INSTALL_EVENT
        else:
            type_name = EVENT_TYPES.NODE_INSTALL_EVENT_FAILED
    elif node.status == NODE_STATUS.DEPLOYED and result in ["FAIL"]:
        type_name = EVENT_TYPES.NODE_POST_INSTALL_EVENT_FAILED
    elif node.status == NODE_STATUS.ENTERING_RESCUE_MODE:
        if result in ["SUCCESS", None]:
            type_name = EVENT_TYPES.NODE_ENTERING_RESCUE_MODE_EVENT
        else:
            type_name = EVENT_TYPES.NODE_ENTERING_RESCUE_MODE_EVENT_FAILED
    elif node.node_type in [
        NODE_TYPE.RACK_CONTROLLER,
        NODE_TYPE.REGION_AND_RACK_CONTROLLER,
    ]:
        type_name = EVENT_TYPES.REQUEST_CONTROLLER_REFRESH
    else:
        type_name = EVENT_TYPES.NODE_STATUS_EVENT

    # Create an extra event for the machine status messages.
    if action in EVENT_STATUS_MESSAGES and event_type == "start":
        Event.objects.register_event_and_event_type(
            EVENT_STATUS_MESSAGES[action],
            type_level=EVENT_DETAILS[EVENT_STATUS_MESSAGES[action]].level,
            type_description=EVENT_DETAILS[
                EVENT_STATUS_MESSAGES[action]
            ].description,
            event_action=action,
            system_id=node.system_id,
            created=created,
        )

    return Event.objects.register_event_and_event_type(
        type_name,
        type_level=EVENT_DETAILS[type_name].level,
        type_description=EVENT_DETAILS[type_name].description,
        event_action=action,
        event_description=f"'{origin}' {description}",
        system_id=node.system_id,
        created=created,
    )


_EXT_TO_KEY = {".out": "stdout", ".err": "stderr", ".yaml": "result"}


def process_file(
    results,
    script_set,
    script_name,
    content,
    request,
    default_exit_status=None,
):
    """Process a file sent to MAAS over the metadata service."""

    script_result_id = get_optional_param(
        request, "script_result_id", None, Int
    )

    # The .out or .err indicates this should be stored in the stdout or stderr
    # column of ScriptResult. If neither are given put it in the combined
    # output column. If given, we look up by script_result_id along with the
    # name to allow .out or .err in the name.
    base_name, output_type = os.path.splitext(script_name)
    key = _EXT_TO_KEY.get(output_type.lower())
    if key is None:
        key = "output"
    else:
        script_name = base_name

    script_result = script_set.scriptresult_set.filter(
        id=script_result_id
    ).first()
    if script_result is None:
        script_id = (
            Script.objects.filter(name=script_name)
            .values_list("id", flat=True)
            .first()
        )
        script_result, _ = script_set.scriptresult_set.get_or_create(
            script_name=script_name,
            defaults={
                "script_id": script_id,
                "status": SCRIPT_STATUS.RUNNING,
            },
        )

    # Store the processed file in the given results dictionary. This allows
    # requests with multipart file uploads to include STDOUT and STDERR.
    if script_result in results:
        results[script_result][key] = content
    else:
        # Internally this is called exit_status, cloud-init sends this as
        # result, using the StatusHandler, and previously the commissioning
        # scripts sent this as script_result.
        for exit_status_name in ["exit_status", "script_result", "result"]:
            exit_status = get_optional_param(
                request, exit_status_name, None, Int
            )
            if exit_status is not None:
                break
        if exit_status is None:
            if default_exit_status is None:
                exit_status = 0
            else:
                exit_status = default_exit_status

        results[script_result] = {"exit_status": exit_status, key: content}

        script_version_id = get_optional_param(
            request, "script_version_id", None, Int
        )
        if script_version_id:
            results[script_result]["script_version_id"] = script_version_id

        runtime = get_optional_param(request, "runtime", None, Number)
        if runtime:
            results[script_result]["runtime"] = runtime


def store_node_power_parameters(node, request):
    """Store power parameters in request.

    The parameters should be JSON, passed with key `power_parameters`.
    """
    power_type = request.POST.get("power_type", None)
    if power_type is None:
        return
    # Don't overwrite redfish power type with ipmi.
    if node.power_type == "redfish":
        power_type = node.power_type

    power_types = list(get_driver_types())
    if not power_types:
        raise ClusterUnavailable(
            "No rack controllers connected to validate the power_type."
        )

    if power_type not in power_types + [UNKNOWN_POWER_TYPE]:
        raise MAASAPIBadRequest("Bad power_type '%s'" % power_type)

    power_parameters = request.POST.get("power_parameters", None)
    if power_parameters:
        try:
            power_parameters = json.loads(power_parameters)
        except ValueError:
            raise MAASAPIBadRequest("Failed to parse JSON power_parameters")
    else:
        power_parameters = node.get_power_parameters()
    if power_type == "redfish":
        power_parameters = {
            **node.get_instance_power_parameters(),
            **power_parameters,
        }
    node.set_power_config(
        power_type, power_parameters, from_commissioning=True
    )
    node.save()


class MetadataViewHandler(OperationsHandler):
    create = update = delete = None

    def read(self, request, mac=None):
        return make_list_response(sorted(self.subfields))


class IndexHandler(MetadataViewHandler):
    """Top-level metadata listing."""

    subfields = ("latest", "2012-03-01")


class StatusHandler(MetadataViewHandler):
    read = update = delete = None

    def create(self, request, system_id):
        """Receive and process a status message from a node, usually cloud-init

        A node can call this to report progress of its booting or deployment.

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

        `script_result_id`, when present, MAAS will search for an existing
        ScriptResult with the given id to store files present.

        """
        # This no longer does anything. This only remains for API
        # documentation, all operations are now performed by the
        # `api_twisted.StatusHandlerResource.render_POST`.
        raise AttributeError(
            "api_twisted.StatusHandlerResource.render_POST should "
            "be used instead."
        )


def try_or_log_event(
    machine, signal_status, error_message, func, *args, **kwargs
):
    """
    Attempts to run the specified function, related to the specified node and
    signal status. Will log the specified error, and create a node event,
    if the function fails.

    If the function raises a retryable failure, will re-raise the exception so
    that a retry can be attempted.

    :param machine: The machine related to the attempted action. Will be used
        in order to log an event, if the function raises an exception.
    :param signal_status: The initial SIGNAL_STATUS, which will be returned
        as-is if no exception occurs. If an exception occurs,
        SIGNAL_STATUS.FAILED will be returned.
    :param error_message: The error message for the log (and node event log) if
        an exception occurs.
    :param func: The function which will be attempted
    :param args: Arguments to pass to the function to be attempted.
    :param kwargs: Keyword arguments to pass to the function to be attempted.
    :return:
    """
    try:
        func(*args, **kwargs)
    except BaseException as e:
        if is_retryable_failure(e):
            # Not the fault of the post-processing function, so
            # re-raise so that the retry mechanism does its job.
            raise
        log.err(None, error_message)
        Event.objects.create_node_event(
            system_id=machine.system_id,
            event_type=EVENT_TYPES.SCRIPT_RESULT_ERROR,
            event_description=error_message,
        )
        signal_status = SIGNAL_STATUS.FAILED
    return signal_status


class EnlistVersionIndexHandler(OperationsHandler):
    create = update = delete = None
    subfields = ("meta-data", "user-data")

    def read(self, request, version):
        return make_list_response(sorted(self.subfields))


class VersionIndexHandler(MetadataViewHandler):
    """Listing for a given metadata version."""

    create = update = delete = None
    subfields = ("maas-commissioning-scripts", "meta-data", "user-data")
    anonymous = EnlistVersionIndexHandler

    # States in which a node is allowed to signal. Only in these states
    # will signaling have an effect.
    signalable_states = [
        NODE_STATUS.BROKEN,
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.FAILED_COMMISSIONING,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.FAILED_DEPLOYMENT,
        NODE_STATUS.READY,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.ENTERING_RESCUE_MODE,
        NODE_STATUS.RESCUE_MODE,
        NODE_STATUS.FAILED_ENTERING_RESCUE_MODE,
        NODE_STATUS.TESTING,
        NODE_STATUS.FAILED_TESTING,
        NODE_STATUS.NEW,
    ]

    effective_signalable_states = [
        NODE_STATUS.COMMISSIONING,
        NODE_STATUS.DEPLOYING,
        NODE_STATUS.DISK_ERASING,
        NODE_STATUS.ENTERING_RESCUE_MODE,
        NODE_STATUS.RESCUE_MODE,
        NODE_STATUS.TESTING,
        NODE_STATUS.NEW,
    ]

    def read(self, request, version, mac=None):
        """Read the metadata index for this version."""
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        if NodeUserData.objects.has_user_data(node):
            shown_subfields = self.subfields
        else:
            shown_subfields = list(self.subfields)
            shown_subfields.remove("user-data")
        return make_list_response(sorted(shown_subfields))

    def _store_results(self, node, script_set, request, status):
        """Store uploaded results."""
        # Group files together with the ScriptResult they belong.
        results = {}
        for script_name, uploaded_file in request.FILES.items():
            content = uploaded_file.read()
            process_file(
                results, script_set, script_name, content, request.POST
            )

        # Commit results to the database.
        for script_result, args in results.items():
            script_result.store_result(
                **args, timedout=(status == SIGNAL_STATUS.TIMEDOUT)
            )

        script_set.last_ping = datetime.now()
        script_set.save()

        if status == SIGNAL_STATUS.APPLYING_NETCONF:
            script_result_id = get_optional_param(
                request.POST, "script_result_id", None, Int
            )
            if script_result_id is not None:
                script_result = script_set.find_script_result(script_result_id)
                # Only update the script status if it was in a pending state
                # incase the script result has been uploaded and proceeded
                # already.
                if script_result.status == SCRIPT_STATUS.PENDING:
                    script_result.status = SCRIPT_STATUS.APPLYING_NETCONF
                    script_result.save(update_fields=["status"])
        if status == SIGNAL_STATUS.INSTALLING:
            script_result_id = get_optional_param(
                request.POST, "script_result_id", None, Int
            )
            if script_result_id is not None:
                script_result = script_set.find_script_result(script_result_id)
                # Only update the script status if it was in a pending state
                # incase the script result has been uploaded and proceeded
                # already.
                if script_result.status in [
                    SCRIPT_STATUS.PENDING,
                    SCRIPT_STATUS.APPLYING_NETCONF,
                ]:
                    script_result.status = SCRIPT_STATUS.INSTALLING
                    script_result.save(update_fields=["status"])
        elif status == SIGNAL_STATUS.WORKING:
            script_result_id = get_optional_param(
                request.POST, "script_result_id", None, Int
            )
            script_name = get_optional_param(
                request.POST, "name", None, String
            )
            script_result = script_set.find_script_result(
                script_result_id, script_name
            )
            if script_result:
                # Only update the script status if it was in a pending or
                # installing state incase the script result has been uploaded
                # and proceeded already.
                if script_result.status in [
                    SCRIPT_STATUS.PENDING,
                    SCRIPT_STATUS.APPLYING_NETCONF,
                    SCRIPT_STATUS.INSTALLING,
                ]:
                    script_result.status = SCRIPT_STATUS.RUNNING
                    script_result.save(update_fields=["status"])
        if node.enable_hw_sync:
            node.last_sync = datetime.now()
            node.save()

    def _process_new(self, node, request, status):
        if status != SIGNAL_STATUS.COMMISSIONING:
            # MAAS only cares if a NEW node is trying to commission itself.
            # Ignore other signals.
            return None

        # Check if the node currently has a pending or running commissioning
        # ScriptSet. If it doesn't create one with only the builtin
        # commissioning Scripts.
        script_set = node.current_commissioning_script_set
        if script_set is None or script_set.status not in (
            SCRIPT_STATUS_RUNNING_OR_PENDING
        ):
            script_set = ScriptSet.objects.create_commissioning_script_set(
                node, scripts=["none"]
            )
            node.current_commissioning_script_set = script_set

        return NODE_STATUS.COMMISSIONING

    def _process_testing(self, node, request, status):
        # node.status_expires is only used to ensure the node boots into
        # testing. After testing has started the script_reaper makes sure the
        # node is still operating.
        if node.status_expires is not None:
            node.status_expires = None
            node.save(update_fields=["status_expires"])

        self._store_results(
            node, node.current_testing_script_set, request, status
        )

        if status == SIGNAL_STATUS.OK:
            enlisting = NodeMetadata.objects.filter(
                node=node, key="enlisting"
            ).first()
            if enlisting is not None:
                enlisting.delete()
                return NODE_STATUS.NEW
            elif node.previous_status in NODE_TESTING_RESET_READY_TRANSITIONS:
                return NODE_STATUS.READY
            elif node.previous_status == NODE_STATUS.FAILED_COMMISSIONING:
                return NODE_STATUS.NEW
            else:
                return node.previous_status
        elif status == SIGNAL_STATUS.FAILED:
            return NODE_STATUS.FAILED_TESTING
        else:
            return None

    def _process_commissioning(self, node, request, status):
        # node.status_expires is only used to ensure the node boots into
        # commissioning. After commissioning has started the script_reaper
        # makes sure the node is still operating.
        if node.status_expires is not None:
            node.status_expires = None
            node.save(update_fields=["status_expires"])

        self._store_results(
            node, node.current_commissioning_script_set, request, status
        )

        # This is skipped when its the rack controller using this endpoint.
        if node.node_type not in (
            NODE_TYPE.RACK_CONTROLLER,
            NODE_TYPE.REGION_CONTROLLER,
            NODE_TYPE.REGION_AND_RACK_CONTROLLER,
        ):
            # XXX 2014-10-21 newell, bug=1382075
            # Auto detection for IPMI tries to save power parameters
            # for Moonshot.  This causes issues if the node's power
            # type is already mscm as it uses SSH instead of IPMI.
            # This fix is temporary as power parameters should not be
            # overwritten during commissioning because MAAS already has
            # knowledge to boot the node.
            # See MP discussion bug=1389808, for further details on why
            # we are using bug fix 1382075 here.
            if node.power_type != "mscm":
                store_node_power_parameters(node, request)

        signaling_statuses = {
            SIGNAL_STATUS.OK: NODE_STATUS.READY,
            SIGNAL_STATUS.FAILED: NODE_STATUS.FAILED_COMMISSIONING,
            SIGNAL_STATUS.TESTING: NODE_STATUS.TESTING,
        }
        target_status = signaling_statuses.get(status)
        enlisting = NodeMetadata.objects.filter(
            node=node, key="enlisting"
        ).first()
        if enlisting is not None and target_status in [
            NODE_STATUS.READY,
            NODE_STATUS.FAILED_COMMISSIONING,
        ]:
            enlisting.delete()
            if target_status == NODE_STATUS.READY:
                target_status = NODE_STATUS.NEW

        if target_status in [
            NODE_STATUS.NEW,
            NODE_STATUS.READY,
            NODE_STATUS.TESTING,
        ]:
            # Commissioning has ended. Check if any scripts failed during
            # post-processing; if so, the commissioning counts as a failure.
            qs = node.current_commissioning_script_set.scriptresult_set.filter(
                status=SCRIPT_STATUS.FAILED
            )
            if qs.exists():
                target_status = NODE_STATUS.FAILED_COMMISSIONING
            else:
                # Recalculate tags when commissioning ends.
                try_or_log_event(
                    node,
                    status,
                    "Failed to update tags.",
                    populate_tags_for_single_node,
                    Tag.objects.exclude(definition=None),
                    node,
                )

        if (
            target_status == NODE_STATUS.FAILED_COMMISSIONING
            and node.current_testing_script_set is not None
        ):
            # If commissioning failed, testing doesn't run; mark any pending
            # scripts as aborted.
            qs = node.current_testing_script_set.scriptresult_set.filter(
                status=SCRIPT_STATUS.PENDING
            )
            qs.update(status=SCRIPT_STATUS.ABORTED, updated=now())

        return target_status

    def _process_deploying(self, node, request, status):
        self._store_results(
            node, node.current_installation_script_set, request, status
        )
        if status == SIGNAL_STATUS.FAILED:
            node.mark_failed(
                comment="Installation failed (refer to the installation log "
                "for more information)."
            )
        return None

    def _process_disk_erasing(self, node, request, status):
        if status == SIGNAL_STATUS.OK:
            # disk erasing complete, release node
            node.release()
        elif status == SIGNAL_STATUS.FAILED:
            node.mark_failed(comment="Failed to erase disks.")
        return None

    def _process_entering_rescue_mode(self, node, request, status):
        if status in (SIGNAL_STATUS.OK, SIGNAL_STATUS.WORKING):
            # entering rescue mode completed, set status
            return NODE_STATUS.RESCUE_MODE
        elif status == SIGNAL_STATUS.FAILED:
            node.mark_failed(comment="Failed to enter rescue mode.")
        return None

    def _process_rescue_mode(self, node, request, status):
        self._store_results(
            node, node.current_commissioning_script_set, request, status
        )
        return None

    @operation(idempotent=False)
    def signal(self, request, version=None, mac=None):
        """Signal ephemeral environment status.

        A node booted into an ephemeral environment can call this to report
        progress of any scripts given to it by MAAS.

        Calling this from a node in an invalid state is an error.  Signaling
        completion more than once is not an error; all but the first
        successful call are ignored.

        :param status: An ephemeral environment signal. This may be "OK" to
            signal completion, WORKING for progress reports, FAILED for,
            FAILURE, COMMISSIONING for requesting the node be put into
            COMMISSIONING when NEW, TESTING for requesting the node be put
            into TESTING from COMMISSIONING, TIMEDOUT if the script has run
            past its time limit, INSTALLING when packages are being installed,
            or APPLYING_NETCONF when custom network configuration is being
            applied.
        :param error: An optional error string. If given, this will be stored
            (overwriting any previous error string), and displayed in the MAAS
            UI. If not given, any previous error string will be cleared.
        :param script_result_id: What ScriptResult this signal is for. If the
            signal contains a file upload the id will be used to find the
            ScriptResult row. If the status is "WORKING" the ScriptResult
            status will be set to running.
        :param exit_status: The return code of the script run.
        """
        node = get_queried_node(request, for_mac=mac)
        status = get_mandatory_param(request.POST, "status", String)
        target_status = None

        # These statuses are acceptable for commissioning, disk erasing,
        # entering rescue mode and deploying.
        if status not in [choice[0] for choice in SIGNAL_STATUS_CHOICES]:
            raise MAASAPIBadRequest("Unknown status: '%s'" % status)

        if node.is_machine:
            process_status_dict = {
                NODE_STATUS.NEW: self._process_new,
                NODE_STATUS.TESTING: self._process_testing,
                NODE_STATUS.COMMISSIONING: self._process_commissioning,
                NODE_STATUS.DEPLOYING: self._process_deploying,
                NODE_STATUS.DEPLOYED: self._process_commissioning,
                NODE_STATUS.DISK_ERASING: self._process_disk_erasing,
                NODE_STATUS.ENTERING_RESCUE_MODE: self._process_entering_rescue_mode,
                NODE_STATUS.RESCUE_MODE: self._process_rescue_mode,
            }
            if node.status in process_status_dict:
                process = process_status_dict[node.status]
            elif node.status in self.signalable_states:
                # If commissioning, it is already registered.  Nothing to be
                # done. If it is installing, should be in deploying state.
                return rc.ALL_OK
            else:
                raise NodeStateViolation(
                    "Machine status isn't valid (status is %s)"
                    % NODE_STATUS_CHOICES_DICT[node.status]
                )
        else:
            # Non-machine nodes can send testing results when in testing
            # state, otherwise accept all signals as commissioning signals
            # regardless of the node's state. This is because devices and
            # controllers which were not deployed by MAAS will be in a NEW
            # or other unknown state but may send commissioning data.
            if node.status == NODE_STATUS.TESTING:
                process = self._process_testing
            else:
                process = self._process_commissioning

        target_status = process(node, request, status)

        # Create appropriate status messages.
        if target_status == NODE_STATUS.READY:
            Event.objects.create_node_event(node, EVENT_TYPES.READY)
        elif target_status == NODE_STATUS.FAILED_COMMISSIONING:
            Event.objects.create_node_event(
                node, EVENT_TYPES.FAILED_COMMISSIONING
            )
        elif target_status == NODE_STATUS.RESCUE_MODE:
            Event.objects.create_node_event(node, EVENT_TYPES.RESCUE_MODE)
        elif target_status == NODE_STATUS.NEW:
            Event.objects.create_node_event(node, EVENT_TYPES.NEW)
        elif target_status == NODE_STATUS.FAILED_TESTING:
            Event.objects.create_node_event(node, EVENT_TYPES.FAILED_TESTING)

        if target_status in (None, node.status):
            # No status change.  Nothing to be done.
            return rc.ALL_OK
        elif target_status in FAILED_STATUSES:
            ScriptResult.objects.filter(
                script_set__in=[
                    node.current_commissioning_script_set,
                    node.current_testing_script_set,
                    node.current_installation_script_set,
                ],
                status__in=SCRIPT_STATUS_RUNNING_OR_PENDING,
            ).update(status=SCRIPT_STATUS.ABORTED, updated=now())

        # Only machines can change their status. This is to allow controllers
        # to send refresh data without having their status changed to READY.
        # The exception to this is if testing was run.
        if (
            node.node_type == NODE_TYPE.MACHINE
            or node.status == NODE_STATUS.TESTING
        ):
            node.update_status(target_status)

        node.error = get_optional_param(request.POST, "error", "", String)

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
        node.set_boot_order(False)
        return rc.ALL_OK

    @operation(idempotent=False)
    def netboot_on(self, request, version=None, mac=None):
        """Turn on netboot on the node."""
        node = get_queried_node(request, for_mac=mac)
        node.set_netboot(True)
        node.set_boot_order(True)
        return rc.ALL_OK


class EnlistMetaDataHandler(OperationsHandler):
    """this has to handle the 'meta-data' portion of the meta-data api
    for enlistment only.  It should mimic the read-only portion
    of /VersionIndexHandler"""

    create = update = delete = None

    data = {
        "instance-id": "i-maas-enlistment",
        "local-hostname": "maas-enlisting-node",
        "public-keys": "",
    }

    def read(self, request, version, item=None):
        check_version(version)

        # Requesting the list of attributes, not any particular attribute.
        if item is None or len(item) == 0:
            keys = sorted(self.data.keys())
            # There's nothing in public-keys, so we don't advertise it.
            # But cloud-init does ask for it and it's not worth logging
            # a traceback for.
            keys.remove("public-keys")
            return make_list_response(keys)

        if item not in self.data:
            raise MAASAPINotFound("Unknown metadata attribute: %s" % item)

        return make_text_response(self.data[item])


class MetaDataHandler(VersionIndexHandler):
    """Meta-data listing for a given version."""

    anonymous = EnlistMetaDataHandler

    subfields = (
        "instance-id",
        "local-hostname",
        "public-keys",
        "vendor-data",
        "x509",
    )

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
        subfield = item.split("/")[0]
        if subfield not in self.subfields:
            raise MAASAPINotFound("Unknown metadata attribute: %s" % subfield)

        producers = {
            "instance-id": self.instance_id,
            "local-hostname": self.local_hostname,
            "public-keys": self.public_keys,
            "vendor-data": self.vendor_data,
            "x509": self.ssl_certs,
        }

        return producers[subfield]

    def read(self, request, version, mac=None, item=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)

        # Requesting the list of attributes, not any particular
        # attribute.
        if item is None or len(item) == 0:
            subfields = list(self.subfields)
            commissioning_without_ssh = (
                node.status == NODE_STATUS.COMMISSIONING
                and not node.enable_ssh
            )
            # Add public-keys to the list of attributes, if the
            # node has registered SSH keys.
            keys = SSHKey.objects.get_keys_for_user(user=node.owner)
            if not keys or commissioning_without_ssh:
                subfields.remove("public-keys")
            return make_list_response(sorted(subfields))

        producer = self.get_attribute_producer(item)
        if producer == self.vendor_data:
            proxy = get_apt_proxy(request, node=node)
            return producer(node, version, item, proxy)
        else:
            return producer(node, version, item)

    def local_hostname(self, node, version, item):
        """Produce local-hostname attribute."""
        return make_text_response(node.fqdn)

    def instance_id(self, node, version, item):
        """Produce instance-id attribute."""
        return make_text_response(node.system_id)

    def vendor_data(self, node, version, item, proxy):
        vendor_data = {
            "cloud-init": "#cloud-config\n%s"
            % yaml.safe_dump(get_vendor_data(node, proxy))
        }
        vendor_data_dump = yaml.safe_dump(
            vendor_data, encoding="utf-8", default_flow_style=False
        )
        # Use the same Content-Type as Piston 3 for YAML content.
        return HttpResponse(
            vendor_data_dump, content_type="application/x-yaml; charset=utf-8"
        )

    def public_keys(self, node, version, item):
        """Produce public-keys attribute."""
        return make_list_response(
            SSHKey.objects.get_keys_for_user(user=node.owner)
        )

    def ssl_certs(self, node, version, item):
        """Produce x509 certs attribute."""
        return make_list_response(
            SSLKey.objects.get_keys_for_user(user=node.owner)
        )


class EnlistUserDataHandler(OperationsHandler):
    """User-data for the enlistment environment"""

    def read(self, request, version):
        check_version(version)
        rack_controller = find_rack_controller(request)
        # XXX: Set a charset for text/plain. Django automatically encodes
        # non-binary content using DEFAULT_CHARSET (which is UTF-8 by default)
        # but only sets the charset parameter in the content-type header when
        # a content-type is NOT provided.
        return HttpResponse(
            generate_user_data_for_status(
                None,
                NODE_STATUS.NEW,
                rack_controller=rack_controller,
                request=request,
            ),
            content_type="text/plain",
        )


class UserDataHandler(MetadataViewHandler):
    """User-data blob for a given version."""

    anonymous = EnlistUserDataHandler

    def read(self, request, version, mac=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        try:
            # When a node is deploying, cloud-init's request
            # for user-data is when MAAS hands the node
            # off to a user.
            if node.status == NODE_STATUS.DEPLOYING:
                if node.install_kvm or node.register_vmhost:
                    # Rather than ending deployment here, note that we're
                    # deploying a VM host.
                    node.agent_name = "maas-kvm-pod"
                    node.save()
                else:
                    # MAAS currently considers a machine "Deployed" when the
                    # cloud-init user data is requested. Note that this doesn't
                    # mean the machine is ready for use yet; cloud-init will
                    # also send a 'finish' event for the 'modules-final'
                    # activity name. However, that check is ambiguous because
                    # it occurs both when curtin is installing, and when
                    # the machine reboots to finish its deployment.
                    node.end_deployment()
            # If this node is supposed to be powered off, serve the
            # 'poweroff' userdata.
            if node.get_boot_purpose() == "poweroff":
                user_data = generate_user_data_for_poweroff(
                    node=node, request=request
                )
            else:
                user_data = NodeUserData.objects.get_user_data(node)
                # user-data must be sent as plain text or MIME encoded. If the
                # user uploaded user_data base64 encoded decode it.
                try:
                    # Check if its valid base64 data with no new lines or spaces.
                    user_data_decoded = base64.b64decode(
                        user_data, validate=True
                    )
                    user_data_stripped = None
                except Exception:
                    # Check if its valid base64 data with new lines or spaces.
                    try:
                        # Remove new lines and spaces, validator chokes on them.
                        user_data_stripped = "".join(
                            [x.strip() for x in user_data.decode().split()]
                        ).encode()
                        user_data_decoded = base64.b64decode(
                            user_data_stripped, validate=True
                        )
                    except Exception:
                        # Data can't be decoded either way, send it as is.
                        user_data_decoded = None
                # If the encoded user_data is the same as the decoded data its base64 encoded.
                if user_data_decoded is not None and base64.b64encode(
                    user_data_decoded
                ) in {user_data, user_data_stripped}:
                    user_data = user_data_decoded
            if node.status == NODE_STATUS.COMMISSIONING:
                # Create a status message for GATHERING_INFO.
                Event.objects.create_node_event(
                    node, EVENT_TYPES.GATHERING_INFO
                )
            return HttpResponse(
                user_data, content_type="application/octet-stream"
            )
        except NodeUserData.DoesNotExist:
            logger.info(
                "No user data registered for node named %s" % node.hostname
            )
            return HttpResponse(status=int(http.client.NOT_FOUND))


class CurtinUserDataHandler(MetadataViewHandler):
    """Curtin user-data blob for a given version."""

    def read(self, request, version, mac=None):
        check_version(version)
        node = get_queried_node(request, for_mac=mac)
        user_data = get_curtin_userdata(request, node)
        return HttpResponse(user_data, content_type="application/octet-stream")


def add_file_to_tar(tar, path, content, mtime, permission=0o755):
    """Add a script to a tar."""
    assert isinstance(content, bytes), "Script content must be binary."
    tarinfo = tarfile.TarInfo(name=path)
    tarinfo.size = len(content)
    tarinfo.mode = permission
    # Modification time defaults to Epoch, which elicits annoying
    # warnings when decompressing.
    tarinfo.mtime = mtime
    tar.addfile(tarinfo, BytesIO(content))


class CommissioningScriptsHandler(MetadataViewHandler):
    """Return a tar archive containing the commissioning scripts.

    This endpoint is deprecated in favor of MAASScriptsHandler below.
    """

    def _iter_scripts(self):
        for script in Script.objects.filter(
            script_type=SCRIPT_TYPE.COMMISSIONING
        ):
            try:
                # Check if the script is a base64 encoded binary.
                content = base64.b64decode(script.script.data)
            except Exception:
                # If it isn't encode the text as binary data.
                content = script.script.data.encode()
            yield script.name, content

    def _get_archive(self):
        """Produce a tar archive of all commissionig scripts.

        Each of the scripts will be in the `ARCHIVE_PREFIX` directory.
        """
        binary = BytesIO()
        scripts = sorted(self._iter_scripts())
        with tarfile.open(mode="w", fileobj=binary) as tarball:
            add_script = partial(add_file_to_tar, tarball, mtime=time.time())
            for name, content in scripts:
                add_script(os.path.join("commissioning.d", name), content)
        return binary.getvalue()

    def read(self, request, version, mac=None):
        check_version(version)
        return HttpResponse(
            self._get_archive(), content_type="application/tar"
        )


class AnonMAASScriptsHandler(AnonymousOperationsHandler):
    """Anonymous access to download node-scripts.

    Enlistment starts by downloading the builtin commissioning scripts
    anonymously. Once BMC detection has finished the machine is created
    the client will switch to the authenticated endpoint.
    """

    create = update = delete = None

    def read(self, request, version, mac=None):
        # Administrator has turned off commissioning during enlistment.
        binary = BytesIO()
        mtime = time.time()
        tar_meta_data = {"commissioning_scripts": []}
        qs = Script.objects.filter(
            script_type=SCRIPT_TYPE.COMMISSIONING
        ).exclude(
            # Network configuration is based on node configuration however
            # the node doesn't exist yet. Once the node is created the
            # client will rerequest the NodeScripts tar which may include
            # scripts which test networking.
            apply_configured_networking=True
        )
        if Config.objects.get_config("enlist_commissioning"):
            qs = qs.filter(Q(default=True) | Q(tags__overlap=["enlisting"]))
        else:
            qs = qs.filter(tags__overlap=["bmc-config"])
        qs = qs.order_by("name").select_related("script")
        # Responses are currently gzip compressed using
        # django.middleware.gzip.GZipMiddleware.
        with tarfile.open(mode="w", fileobj=binary) as tar:
            for script in qs:
                # Return the default parameter fields for any commissioning
                # script. An empty Node() is passed so the form knows its
                # validating input and returning defaults. The form only
                # uses the Node object to fill in storage or interface
                # parameters. When none are found "all" is used which is
                # handled elsewhere.
                form = ParametersForm(data={}, script=script, node=Node())
                # The form isn't valid if there is a required field with no
                # default value.
                if not form.is_valid():
                    logger.error(
                        "Unable to send commissioning script to enlisting "
                        f"machine - {form.errors}"
                    )
                    continue
                path = os.path.join("commissioning", script.name)
                content = script.script.data.encode()
                add_file_to_tar(tar, path, content, mtime)
                for parameters in form.cleaned_data["input"]:
                    tar_meta_data["commissioning_scripts"].append(
                        {
                            "name": script.name,
                            "path": path,
                            "script_version_id": script.script.id,
                            "timeout_seconds": script.timeout.total_seconds(),
                            "parallel": script.parallel,
                            "hardware_type": script.hardware_type,
                            "parameters": parameters,
                            "packages": script.packages,
                            "for_hardware": script.for_hardware,
                            "apply_configured_networking": (
                                script.apply_configured_networking
                            ),
                        }
                    )
            add_file_to_tar(
                tar,
                "index.json",
                json.dumps({"1.0": tar_meta_data}).encode(),
                mtime,
                0o644,
            )
        return HttpResponse(
            binary.getvalue(), content_type="application/x-tar"
        )


def get_script_result_properties(script_result):
    return {
        "name": script_result.name,
        "script_result_id": script_result.id,
        "script_version_id": script_result.script.script.id,
        "timeout_seconds": (script_result.script.timeout.total_seconds()),
        "parallel": script_result.script.parallel,
        "hardware_type": script_result.script.hardware_type,
        "parameters": script_result.parameters,
        "packages": script_result.script.packages,
        "for_hardware": script_result.script.for_hardware,
        "apply_configured_networking": (
            script_result.script.apply_configured_networking
        ),
        "has_started": script_result.status != SCRIPT_STATUS.PENDING,
        "has_finished": (
            script_result.status not in SCRIPT_STATUS_RUNNING_OR_PENDING
        ),
        "default": script_result.script.default,
        "tags": script_result.script.tags,
    }


class MAASScriptsHandler(OperationsHandler):
    anonymous = AnonMAASScriptsHandler

    def _add_script_set_to_tar(
        self, script_set, tar, prefix, mtime, include_finished=False
    ):
        if script_set is None:
            return []
        meta_data = []
        for script_result in script_set:
            # Don't rerun Scripts which have already run.
            if (
                not include_finished
                and script_result.status
                not in SCRIPT_STATUS_RUNNING_OR_PENDING
            ):
                continue

            path = os.path.join(prefix, script_result.name)
            md_item = {}
            if script_result.script is None:
                # Script was deleted by the user and it is not a builtin
                # commissioning script. Don't expect a result.
                script_result.delete()
                continue
            content = script_result.script.script.data.encode()
            add_file_to_tar(tar, path, content, mtime)
            md_item = get_script_result_properties(script_result)
            md_item["path"] = path
            if md_item["has_started"]:
                # If the script has already started send any results MAAS has
                # received. The script runner will append these files and send
                # them back when done.
                out_path = os.path.join(
                    "out", f"{script_result.name}.{script_result.id}"
                )
                add_file_to_tar(tar, out_path, script_result.output, mtime)
                add_file_to_tar(
                    tar, "%s.out" % out_path, script_result.stdout, mtime
                )
                add_file_to_tar(
                    tar, "%s.err" % out_path, script_result.stderr, mtime
                )
                add_file_to_tar(
                    tar, "%s.yaml" % out_path, script_result.result, mtime
                )

            # Only generate and add network configuration if the Script needs
            # it and it hasn't already been added.
            if (
                md_item["apply_configured_networking"]
                and NETPLAN_TAR_PATH not in tar.getnames()
            ):
                node = script_result.script_set.node
                # Testing is always done in the commissioning environment.
                configs = Config.objects.get_configs(
                    ["commissioning_osystem", "commissioning_distro_series"]
                )
                network_yaml_settings = get_network_yaml_settings(
                    configs["commissioning_osystem"],
                    configs["commissioning_distro_series"],
                )
                network_config = NodeNetworkConfiguration(
                    node,
                    version=network_yaml_settings.version,
                    source_routing=network_yaml_settings.source_routing,
                )
                network_config_yaml = yaml.safe_dump(
                    network_config.config, default_flow_style=False
                )
                add_file_to_tar(
                    tar,
                    NETPLAN_TAR_PATH,
                    network_config_yaml.encode(),
                    mtime,
                    0o644,
                )

            meta_data.append(md_item)

        return meta_data

    def read(self, request, version, mac=None):
        """Returns a tar containing user and status selected scripts.

        The tar produced will contain scripts which are set to be run during
        a node's status and/or user selected scripts. The tar is currently
        uncompressed as all API requests are already gziped. This may change
        so auto-decompress is suggested. If the node returns a script status
        and calls this request again only the scripts which havn't been run
        will be returned.
        """
        node = get_queried_node(request)
        binary = BytesIO()
        mtime = time.time()
        tar_meta_data = {}
        # Responses are currently gzip compressed using
        # django.middleware.gzip.GZipMiddleware.
        with tarfile.open(mode="w", fileobj=binary) as tar:
            # Commissioning scripts should only be run during commissioning or
            # in rescue mode.
            if (
                node.status
                in (
                    NODE_STATUS.COMMISSIONING,
                    NODE_STATUS.DEPLOYED,
                    NODE_STATUS.ENTERING_RESCUE_MODE,
                    NODE_STATUS.RESCUE_MODE,
                )
                and node.current_commissioning_script_set is not None
            ):
                script_set = node.current_commissioning_script_set
                # Prefetch all the data we need.
                qs = script_set.scriptresult_set.select_related(
                    "script", "script__script"
                )
                # After the script runner finishes sending all commissioning
                # results it redownloads the script tar. It does this in-case
                # a commissioning script discovers hardware associated with
                # hardware identified in the for_hardware field of a script.
                # select_for_hardware_scripts() processes the output of the
                # builtin commissioning scripts and adds any associated script.
                # This does not need to happen the first time the script runner
                # downloads the tar as the region has not yet received new
                # data.
                for script_result in qs:
                    if script_result.status != SCRIPT_STATUS.PENDING:
                        script_set.select_for_hardware_scripts()
                        break
                meta_data = self._add_script_set_to_tar(
                    node.current_commissioning_script_set,
                    tar,
                    "commissioning",
                    mtime,
                    include_finished=node.status == NODE_STATUS.DEPLOYED,
                )
                if meta_data:
                    tar_meta_data["commissioning_scripts"] = sorted(
                        meta_data, key=itemgetter("name", "script_result_id")
                    )

            # Always send testing scripts.
            if node.current_testing_script_set is not None:
                # prefetch all the data we need
                qs = node.current_testing_script_set.scriptresult_set.select_related(
                    "script", "script__script"
                )
                meta_data = self._add_script_set_to_tar(
                    qs, tar, "testing", mtime
                )
                if meta_data:
                    tar_meta_data["testing_scripts"] = sorted(
                        meta_data, key=itemgetter("name", "script_result_id")
                    )

            if not tar_meta_data:
                return HttpResponse(status=int(http.client.NO_CONTENT))

            add_file_to_tar(
                tar,
                "index.json",
                json.dumps({"1.0": tar_meta_data}).encode(),
                mtime,
                0o644,
            )

        return HttpResponse(
            binary.getvalue(), content_type="application/x-tar"
        )


class AnonMetaDataHandler(VersionIndexHandler):
    """Anonymous metadata."""

    @operation(idempotent=True)
    def get_enlist_preseed(self, request, version=None):
        """Render and return a preseed script for enlistment."""
        rack_controller = find_rack_controller(request)
        # XXX: Set a charset for text/plain. Django automatically encodes
        # non-binary content using DEFAULT_CHARSET (which is UTF-8 by default)
        # but only sets the charset parameter in the content-type header when
        # a content-type is NOT provided.
        preseed = get_enlist_preseed(request, rack_controller=rack_controller)
        return HttpResponse(preseed, content_type="text/plain")

    @operation(idempotent=True)
    def get_preseed(self, request, version=None, system_id=None):
        """Render and return a preseed script for the given node."""
        node = get_object_or_404(Node, system_id=system_id)
        # XXX: Set a charset for text/plain. Django automatically encodes
        # non-binary content using DEFAULT_CHARSET (which is UTF-8 by default)
        # but only sets the charset parameter in the content-type header when
        # a content-type is NOT provided.
        preseed = get_preseed(request, node)
        return HttpResponse(preseed, content_type="text/plain")

    @operation(idempotent=False)
    def netboot_off(self, request, version=None, system_id=None):
        """Turn off netboot on the node.

        A commissioning node can call this to turn off netbooting when
        it finishes installing itself.
        """
        node = get_object_or_404(Node, system_id=system_id)
        node.set_netboot(False)
        node.set_boot_order(False)

        # Build and register an event for "node installation finished".
        # This is a best-guess. At the moment, netboot_off() only gets
        # called when the node has finished installing, so it's an
        # accurate predictor of the end of the install process.
        Event.objects.create_node_event(
            node,
            EVENT_TYPES.NODE_INSTALLATION_FINISHED,
            event_description="Node disabled netboot",
        )
        return rc.ALL_OK
