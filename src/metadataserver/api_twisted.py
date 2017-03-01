# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Metadata API that runs in the Twisted reactor."""

import base64
import bz2
from collections import defaultdict
from datetime import datetime
import json

from maasserver.api.utils import extract_oauth_key_from_auth_header
from maasserver.enum import (
    NODE_STATUS,
    NODE_TYPE,
)
from maasserver.utils.orm import (
    in_transaction,
    transactional,
    TransactionManagementError,
)
from maasserver.utils.threads import deferToDatabase
from metadataserver import logger
from metadataserver.api import (
    add_event_to_node_event_log,
    process_file,
)
from metadataserver.models import NodeKey
from provisioningserver.logger import LegacyLogger
from twisted.application.internet import TimerService
from twisted.internet import reactor
from twisted.web.resource import Resource


log = LegacyLogger()


class StatusHandlerResource(Resource):

    # Has no children, so getChild will not be called.
    isLeaf = True

    # Only POST operations are allowed.
    allowedMethods = [b'POST']

    # Required keys in the message.
    requiredMessageKeys = ['event_type', 'origin', 'name', 'description']

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
        authorization = request.getHeader(b'authorization')
        if not authorization:
            request.setResponseCode(401)
            return b""
        authorization = extract_oauth_key_from_auth_header(
            authorization.decode('utf-8'))
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
            return error_msg.encode('ascii')

        try:
            message = json.loads(payload)
        except ValueError:
            request.setResponseCode(400)
            error_msg = "Status payload is not valid JSON:\n%s\n\n" % payload
            logger.error(error_msg)
            return error_msg.encode('ascii')

        # Filter the level early so less messages need to be processed.
        level = message.get('level', None)
        if level is not None and level == "DEBUG":
            # Ignore all debug messages.
            request.setResponseCode(204)
            return b""

        # Ensure the other required keys exist.
        missing_keys = [
            key
            for key in self.requiredMessageKeys
            if key not in message
        ]
        if len(missing_keys) > 0:
            request.setResponseCode(400)
            error_msg = (
                'Missing parameter(s) %s in '
                'status message.' % ', '.join(missing_keys))
            logger.error(error_msg)
            return error_msg.encode('ascii')

        # Queue the message with its authorization in the status worker.
        self.worker.queueMessage(authorization, message)
        request.setResponseCode(204)
        return b""


class StatusWorkerService(TimerService, object):
    """Service to update nodes from recieved status messages."""

    check_interval = 60  # Every second.

    def __init__(self, dbtasks, clock=reactor):
        # Call self._tryUpdateNodes() every self.check_interval.
        super(StatusWorkerService, self).__init__(
            self.check_interval, self._tryUpdateNodes)
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
            key__in=list(queue.keys())).select_related('node')
        return [
            (key.node, queue[key.key])
            for key in keys
        ]

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
                "outside of a transaction.")
        else:
            # Here we're in a database thread, with a database connection.
            for message in messages:
                try:
                    self._processMessage(node, message)
                except:
                    log.err(
                        None,
                        "Failed to process message "
                        "for node: %s" % node.hostname)

    @transactional
    def _processMessage(self, node, message):
        event_type = message['event_type']
        origin = message['origin']
        activity_name = message['name']
        description = message['description']
        result = message.get('result', None)

        # Add this event to the node event log.
        add_event_to_node_event_log(
            node, origin, activity_name, description, result,
            message['timestamp'])

        # Group files together with the ScriptResult they belong.
        results = {}
        for sent_file in message.get('files', []):
            # Set the result type according to the node's status.
            if node.status == NODE_STATUS.TESTING:
                script_set = node.current_testing_script_set
            elif (node.status == NODE_STATUS.COMMISSIONING or
                    node.node_type != NODE_TYPE.MACHINE):
                script_set = node.current_commissioning_script_set
            elif node.status == NODE_STATUS.DEPLOYING:
                script_set = node.current_installation_script_set
            else:
                raise ValueError(
                    "Invalid status for saving files: %d" % node.status)

            script_name = sent_file['path']
            content = self._retrieve_content(
                compression=sent_file.get('compression', None),
                encoding=sent_file['encoding'],
                content=sent_file['content'])
            process_file(results, script_set, script_name, content, sent_file)

        # Commit results to the database.
        for script_result, args in results.items():
            script_result.store_result(**args)

        # Update the last ping in any status which uses a script_set whenever a
        # node in that status contacts us.
        script_set_statuses = {
            NODE_STATUS.COMMISSIONING: node.current_commissioning_script_set,
            NODE_STATUS.TESTING: node.current_testing_script_set,
            NODE_STATUS.DEPLOYING: node.current_installation_script_set,
        }
        script_set = script_set_statuses.get(node.status)
        if script_set is not None:
            script_set.last_ping = message['timestamp']
            script_set.save()

        # At the end of a top-level event, we change the node status.
        save_node = False
        if self._is_top_level(activity_name) and event_type == 'finish':
            if node.status == NODE_STATUS.COMMISSIONING:
                if result in ['FAIL', 'FAILURE']:
                    node.status = NODE_STATUS.FAILED_COMMISSIONING
                    save_node = True
            elif node.status == NODE_STATUS.DEPLOYING:
                if result in ['FAIL', 'FAILURE']:
                    node.mark_failed(
                        comment="Installation failed (refer to the "
                                "installation log for more information).")
                    save_node = True
            elif node.status == NODE_STATUS.DISK_ERASING:
                if result in ['FAIL', 'FAILURE']:
                    node.mark_failed(comment="Failed to erase disks.")
                    save_node = True

            # Deallocate the node if we enter any terminal state.
            if node.node_type == NODE_TYPE.MACHINE and node.status in [
                    NODE_STATUS.READY,
                    NODE_STATUS.FAILED_COMMISSIONING]:
                node.status_expires = None
                node.owner = None
                node.error = 'failed: %s' % description
                save_node = True

        if save_node:
            node.save()

    def _retrieve_content(self, compression, encoding, content):
        """Extract the content of the sent file."""
        # Select the appropriate decompressor.
        if compression is None:
            decompress = lambda s: s
        elif compression == 'bzip2':
            decompress = bz2.decompress
        else:
            raise ValueError('Invalid compression: %s' % compression)

        # Select the appropriate decoder.
        if encoding == 'base64':
            decode = base64.decodebytes
        else:
            raise ValueError('Invalid encoding: %s' % encoding)

        return decompress(decode(content.encode("ascii")))

    def _is_top_level(self, activity_name):
        """Top-level events do not have slashes in their names."""
        return '/' not in activity_name

    def queueMessage(self, authorization, message):
        """Queue message for processing."""
        # Ensure a timestamp exists in the message and convert it to a
        # datetime object. This is used to update the `last_ping` and the
        # time for the event message.
        timestamp = message.get('timestamp', None)
        if timestamp is not None:
            message['timestamp'] = datetime.utcfromtimestamp(
                message['timestamp'])
        else:
            message['timestamp'] = datetime.utcnow()
        self.queue[authorization].append(message)
