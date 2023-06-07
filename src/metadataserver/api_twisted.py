# Copyright 2017-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API that runs in the Twisted reactor."""

import base64
import bz2
from collections import defaultdict
from datetime import datetime
import json

from django.db.utils import DatabaseError
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET

from maasserver.api.utils import extract_oauth_key_from_auth_header
from maasserver.enum import NODE_STATUS, NODE_TYPE
from maasserver.forms.pods import PodForm
from maasserver.models import Interface, Node, NodeMetadata
from maasserver.preseed import CURTIN_INSTALL_LOG
from maasserver.utils.orm import (
    in_transaction,
    transactional,
    TransactionManagementError,
)
from maasserver.utils.threads import deferToDatabase
from maasserver.vmhost import discover_and_sync_vmhost
from metadataserver import logger
from metadataserver.api import add_event_to_node_event_log, process_file
from metadataserver.enum import SCRIPT_STATUS
from metadataserver.models import NodeKey
from metadataserver.vendor_data import (
    LXD_CERTIFICATE_METADATA_KEY,
    VIRSH_PASSWORD_METADATA_KEY,
)
from provisioningserver.certificates import Certificate
from provisioningserver.events import EVENT_STATUS_MESSAGES
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import deferred

log = LegacyLogger()


class StatusHandlerResource(Resource):

    # Has no children, so getChild will not be called.
    isLeaf = True

    # Only POST operations are allowed.
    allowedMethods = [b"POST"]

    # Required keys in the message.
    requiredMessageKeys = ["event_type", "origin", "name", "description"]

    def __init__(self, status_worker):
        self.worker = status_worker

    def render_POST(self, request):
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
        # Extract the authorization from request. This only does a basic
        # check that its provided. The status worker will do the authorization,
        # the negative to this is that the calling client will no know. To
        # them the message was accepted. This overall is okay since they are
        # just status messages.
        authorization = request.getHeader(b"authorization")
        if not authorization:
            request.setResponseCode(401)
            return b""
        authorization = extract_oauth_key_from_auth_header(
            authorization.decode("utf-8")
        )
        if authorization is None:
            request.setResponseCode(401)
            return b""

        # Load the content to ensure that its atleast correct before placing
        # it into the status worker.
        payload = request.content.read()
        try:
            payload = payload.decode("ascii")
        except UnicodeDecodeError as error:
            request.setResponseCode(400)
            error_msg = "Status payload must be ASCII-only: %s" % error
            logger.error(error_msg)
            return error_msg.encode("ascii")

        try:
            message = json.loads(payload)
        except ValueError:
            request.setResponseCode(400)
            error_msg = "Status payload is not valid JSON:\n%s\n\n" % payload
            logger.error(error_msg)
            return error_msg.encode("ascii")

        # Ensure the other required keys exist.
        missing_keys = [
            key for key in self.requiredMessageKeys if key not in message
        ]
        if len(missing_keys) > 0:
            request.setResponseCode(400)
            error_msg = (
                "Missing parameter(s) %s in "
                "status message." % ", ".join(missing_keys)
            )
            logger.error(error_msg)
            return error_msg.encode("ascii")

        # Queue the message with its authorization in the status worker.
        d = self.worker.queueMessage(authorization, message)

        # Finish the request after defer finishes.
        def _finish(result, request):
            request.setResponseCode(204)
            request.finish()

        d.addCallback(_finish, request)
        return NOT_DONE_YET


POD_CREATION_ERROR = (
    "Internal error while creating VM host. (See regiond.log for details.)"
)


def _create_vmhost_for_deployment(node):
    cred_types = set()
    if node.register_vmhost:
        cred_types.add(LXD_CERTIFICATE_METADATA_KEY)
    if node.install_kvm:
        cred_types.add(VIRSH_PASSWORD_METADATA_KEY)

    creds_meta = list(
        NodeMetadata.objects.filter(
            node=node,
            key__in=cred_types,
        )
    )
    if not creds_meta:
        node.mark_failed(
            comment="Failed to deploy VM host: Credentials not found.",
            commit=False,
        )
        return

    # the IP is associated to the bridge the boot interface is in, not the
    # interface itself
    ip = _get_ip_address_for_vmhost(node)

    for cred_meta in creds_meta:
        is_lxd = cred_meta.key == LXD_CERTIFICATE_METADATA_KEY
        secret = cred_meta.value
        cred_meta.delete()

        name = node.hostname
        if len(creds_meta) > 1:
            # make VM host names unique
            name += "-lxd" if is_lxd else "-virsh"

        form_data = {
            "name": name,
            "zone": node.zone.name,
            "pool": node.pool.name,
        }
        if is_lxd:
            certificate = Certificate.from_pem(secret)
            form_data.update(
                {
                    "type": "lxd",
                    "power_address": ip,
                    "certificate": certificate.certificate_pem(),
                    "key": certificate.private_key_pem(),
                    "project": "maas",
                }
            )
        else:
            form_data.update(
                {
                    "type": "virsh",
                    "power_address": f"qemu+ssh://virsh@{ip}/system",
                    "power_pass": secret,
                }
            )
        pod_form = PodForm(data=form_data, user=node.owner)
        if pod_form.is_valid():
            try:
                pod = pod_form.save()
            except DatabaseError:
                # Re-raise database errors, since we want it to be
                # retried if possible. If it's not retriable, we
                # couldn't mark the node as failed anyway, since the
                # transaction will be broken.
                # XXX: We should refactor the processing of messages so
                # that the node is marked failed/deployed in a seperate
                # transaction than the one doing the processing.
                raise
            except Exception as e:
                node.mark_failed(comment=POD_CREATION_ERROR, commit=False)
                log.err(None, f"Error saving VM host: {e}")
                return
            else:
                discover_and_sync_vmhost(pod, node.owner)

        else:
            node.mark_failed(comment=POD_CREATION_ERROR, commit=False)
            log.msg("Error while creating VM host: %s" % dict(pod_form.errors))
            return

    node.status = NODE_STATUS.DEPLOYED


def _get_ip_address_for_vmhost(node):
    boot_interface = node.get_boot_interface()
    interface_ids = {boot_interface.id}

    # recursively find all children interface IDs
    new_ids = {boot_interface.id}
    while new_ids:
        new_ids = set(
            Interface.objects.filter(parents__in=new_ids).values_list(
                "id", flat=True
            )
        )
        interface_ids |= new_ids

    ip = node.ip_addresses(
        ifaces=Interface.objects.filter(id__in=interface_ids)
    )[0]
    if ":" in ip:
        ip = f"[{ip}]"
    return ip


class StatusWorkerService(TimerService):
    """Service to update nodes from recieved status messages."""

    check_interval = 60  # Every second.

    def __init__(self, dbtasks, clock=reactor):
        # Call self._tryUpdateNodes() every self.check_interval.
        super().__init__(self.check_interval, self._tryUpdateNodes)
        self.dbtasks = dbtasks
        self.clock = clock
        self.queue = defaultdict(list)

    def _tryUpdateNodes(self):
        if len(self.queue) != 0:
            queue, self.queue = self.queue, defaultdict(list)
            d = deferToDatabase(self._preProcessQueue, queue)
            d.addCallback(self._processMessagesLater)
            d.addErrback(log.err, "Failed to process node status messages.")
            return d

    @transactional
    def _preProcessQueue(self, queue):
        """Check authorizations.

        Return a list of (node, messages) tuples, where each node is found
        from its authorisation.
        """
        keys = NodeKey.objects.filter(
            key__in=list(queue.keys())
        ).select_related("node")
        return [(key.node, queue[key.key]) for key in keys]

    def _processMessagesLater(self, tasks):
        # Move all messages on the queue off onto the database tasks queue.
        # We're not going to wait for them to be processed because we can't /
        # don't apply back-pressure to those systems that are producing these
        # messages anyway.
        for node, messages in tasks:
            self.dbtasks.addTask(self._processMessages, node, messages)

    def _processMessages(self, node, messages):
        # Push the messages into the database, recording them for this node.
        # This should be called in a non-reactor thread with a pre-existing
        # connection (e.g. via deferToDatabase).
        if in_transaction():
            raise TransactionManagementError(
                "_processMessages must be called from "
                "outside of a transaction."
            )
        else:
            # Here we're in a database thread, with a database connection.
            for idx, message in enumerate(messages):
                try:
                    exists = self._processMessage(node, message)
                    if not exists:
                        # Node has been deleted no reason to continue saving
                        # the events for this node.
                        break
                except Exception:
                    log.err(
                        None,
                        "Failed to process message "
                        "for node: %s" % node.hostname,
                    )

    @transactional
    def _processMessage(self, node, message):
        # Validate that the node still exists since this is a new transaction.
        try:
            node = Node.objects.get(id=node.id)
        except Node.DoesNotExist:
            return False

        event_type = message["event_type"]
        origin = message["origin"]
        activity_name = message["name"]
        description = message["description"]
        result = message.get("result", None)
        # LP:1701352 - If no exit code is given by the client default to
        # 0(pass) unless the signal is fail then set to 1(failure). This allows
        # a Curtin failure to cause the ScriptResult to fail.
        failed = result in ["FAIL", "FAILURE"]
        default_exit_status = 1 if failed else 0

        # Add this event to the node event log if 'start' or a 'failure'.
        if event_type == "start" or failed:
            add_event_to_node_event_log(
                node,
                origin,
                activity_name,
                description,
                event_type,
                result,
                message["timestamp"],
            )

        # Group files together with the ScriptResult they belong.
        results = {}
        for sent_file in message.get("files", []):
            # Set the result type according to the node's status.
            if node.status in (
                NODE_STATUS.TESTING,
                NODE_STATUS.FAILED_TESTING,
            ):
                script_set = node.current_testing_script_set
            elif (
                node.status
                in (
                    NODE_STATUS.COMMISSIONING,
                    NODE_STATUS.FAILED_COMMISSIONING,
                )
                or node.node_type != NODE_TYPE.MACHINE
            ):
                script_set = node.current_commissioning_script_set
            elif node.status in (
                NODE_STATUS.DEPLOYING,
                NODE_STATUS.DEPLOYED,
                NODE_STATUS.FAILED_DEPLOYMENT,
            ):
                script_set = node.current_installation_script_set
            else:
                raise ValueError(
                    "Invalid status for saving files: %d" % node.status
                )

            script_name = sent_file["path"]
            encoding = sent_file.get("encoding")
            content = sent_file.get("content")
            compression = sent_file.get("compression")
            # Only capture files which has sent content. This occurs when
            # Curtin is instructed to post the error_tarfile and no error
            # has occured(LP:1772118). Empty files are still captured as
            # they are sent as the empty string
            if content is not None:
                content = self._retrieve_content(
                    compression, encoding, content
                )
                process_file(
                    results,
                    script_set,
                    script_name,
                    content,
                    sent_file,
                    default_exit_status,
                )

        # Commit results to the database.
        for script_result, args in results.items():
            script_result.store_result(**args)

        # At the end of a top-level event, we change the node status.
        save_node = False
        if self._is_top_level(activity_name) and event_type == "finish":
            if node.status == NODE_STATUS.COMMISSIONING:
                # cloud-init may send a failure message if a script reboots
                # the system. If a script is running which may_reboot ignore
                # the signal.
                if failed:
                    script_set = node.current_commissioning_script_set
                    if (
                        script_set is None
                        or not script_set.scriptresult_set.filter(
                            status=SCRIPT_STATUS.RUNNING,
                            script__may_reboot=True,
                        ).exists()
                    ):
                        node.mark_failed(
                            comment="Commissioning failed, cloud-init "
                            "reported a failure (refer to the event log for "
                            "more information)",
                            commit=False,
                            script_result_status=SCRIPT_STATUS.ABORTED,
                        )
                        save_node = True
            elif node.status == NODE_STATUS.DEPLOYING:
                # XXX: when activity_name == moudles-config, this currently
                # /always/ fails, since MAAS passes two different versions
                # for the apt configuration. The only reason why we don't
                # see additional issues because of this is due to the node
                # already being marked "Deployed". Right now this is prevented
                # only in the VM host deploy case, but we should make this check
                # more general when time allows.
                if failed and not (node.install_kvm or node.register_vmhost):
                    node.mark_failed(
                        comment="Installation failed (refer to the "
                        "installation log for more information).",
                        commit=False,
                    )
                    save_node = True
                elif (
                    not failed
                    and activity_name == "modules-final"
                    and (node.install_kvm or node.register_vmhost)
                    and node.agent_name == "maas-kvm-pod"
                ):
                    save_node = True
                    _create_vmhost_for_deployment(node)
            elif node.status == NODE_STATUS.DISK_ERASING:
                if failed:
                    node.mark_failed(
                        comment="Failed to erase disks.", commit=False
                    )
                    save_node = True
            # Deallocate the node if we enter any terminal state.
            if node.node_type == NODE_TYPE.MACHINE and node.status in [
                NODE_STATUS.READY,
                NODE_STATUS.FAILED_COMMISSIONING,
            ]:
                node.status_expires = None
                node.owner = None
                node.error = "failed: %s" % description
                save_node = True
        elif self._is_top_level(activity_name) and event_type == "start":
            if (
                node.status == NODE_STATUS.DEPLOYING
                and activity_name == "cmd-install"
                and origin == "curtin"
            ):
                script_set = node.current_installation_script_set
                script_result = script_set.find_script_result(
                    script_name=CURTIN_INSTALL_LOG
                )
                script_result.status = SCRIPT_STATUS.RUNNING
                script_result.save(update_fields=["status"])

        # Reset status_expires when Curtin signals its starting or finishing
        # early commands. This allows users to define early or late commands
        # which take up to 40 minutes to run.
        if (
            origin == "curtin"
            and event_type in ["start", "finish"]
            and activity_name
            in [
                "cmd-install/stage-early",
                "cmd-install",
                "cmd-install/stage-late",
            ]
        ):
            node.reset_status_expires()
            save_node = True

        if save_node:
            node.save()
        return True

    def _retrieve_content(self, compression, encoding, content):
        """Extract the content of the sent file."""
        # Select the appropriate decompressor.
        if compression is None:

            def decompress(s):
                return s

        elif compression == "bzip2":
            decompress = bz2.decompress
        else:
            raise ValueError("Invalid compression: %s" % compression)

        # Select the appropriate decoder.
        if encoding == "base64":
            decode = base64.decodebytes
        else:
            raise ValueError("Invalid encoding: %s" % encoding)

        return decompress(decode(content.encode("ascii")))

    def _is_top_level(self, activity_name):
        """Top-level events do not have slashes in their names."""
        return "/" not in activity_name

    def _processMessageNow(self, authorization, message):
        # This should be called in a non-reactor thread with a pre-existing
        # connection (e.g. via deferToDatabase).
        if in_transaction():
            raise TransactionManagementError(
                "_processMessageNow must be called from "
                "outside of a transaction."
            )
        else:
            try:
                node = transactional(NodeKey.objects.get_node_for_key)(
                    authorization
                )
            except NodeKey.DoesNotExist:
                # The node that should get this message has already had its
                # owner cleared or changed and this message cannot be saved.
                return None
            else:
                self._processMessage(node, message)

    @deferred
    def queueMessage(self, authorization, message):
        """Queue message for processing."""
        # Ensure a timestamp exists in the message and convert it to a
        # datetime object. This is used for the time for the event message.
        timestamp = message.get("timestamp", None)
        if timestamp is not None:
            message["timestamp"] = datetime.utcfromtimestamp(
                message["timestamp"]
            )
        else:
            message["timestamp"] = datetime.utcnow()

        # Determine if this messsage needs to be processed immediately.
        is_starting_event = (
            self._is_top_level(message["name"])
            and message["name"] == "cmd-install"
            and message["event_type"] == "start"
            and message["origin"] == "curtin"
        )
        is_final_event = (
            self._is_top_level(message["name"])
            and message["event_type"] == "finish"
        )
        has_files = len(message.get("files", [])) > 0
        # Process Curtin early/late start/finish messages so that
        # status_expires is reset allowing them to take up to 40 min.
        is_curtin_early_late = (
            message["name"]
            in ["cmd-install/stage-early", "cmd-install/stage-late"]
            and message["event_type"] in ["start", "finish"]
            and message["origin"] == "curtin"
        )
        is_status_message_event = (
            message["name"] in EVENT_STATUS_MESSAGES
            and message["event_type"] == "start"
        )
        if (
            is_starting_event
            or is_final_event
            or has_files
            or is_curtin_early_late
            or is_status_message_event
        ):
            d = deferToDatabase(
                self._processMessageNow, authorization, message
            )
            d.addErrback(
                log.err, "Failed to process status message instantly."
            )
            return d
        else:
            self.queue[authorization].append(message)
