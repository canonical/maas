# Copyright 2017-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import base64
import bz2
from datetime import datetime, timedelta, timezone
from io import BytesIO
import json
import random
from unittest import TestCase
from unittest.mock import call, Mock, sentinel

from django.db.utils import DatabaseError
from netaddr import IPAddress
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.web.server import NOT_DONE_YET
from twisted.web.test.requesthelper import DummyRequest

from maasserver.enum import INTERFACE_TYPE, IPADDRESS_TYPE, NODE_STATUS
from maasserver.models import Event, Node, NodeKey, Pod
from maasserver.models import node as node_module
from maasserver.models.signals.testing import SignalsDisabled
from maasserver.models.timestampedmodel import now
from maasserver.node_status import get_node_timeout
from maasserver.preseed import CURTIN_INSTALL_LOG
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import (
    reload_object,
    transactional,
    TransactionManagementError,
)
from maasserver.utils.threads import deferToDatabase
from maastesting.crochet import wait_for
from maastesting.testcase import MAASTestCase
from metadataserver import api
from metadataserver import api_twisted as api_twisted_module
from metadataserver.api_twisted import (
    _create_vmhost_for_deployment,
    POD_CREATION_ERROR,
    StatusHandlerResource,
    StatusWorkerService,
)
from metadataserver.enum import RESULT_TYPE, SCRIPT_STATUS
from provisioningserver.events import EVENT_STATUS_MESSAGES
from provisioningserver.testing.certificates import get_sample_cert

wait_for_reactor = wait_for()


class TestStatusHandlerResource(MAASTestCase):
    def make_request(self, content=None, token=None):
        request = DummyRequest([])
        if token is None:
            token = factory.make_name("token")
        request.requestHeaders.addRawHeader(
            b"authorization", "oauth_token=%s" % token
        )
        if content is not None:
            request.content = BytesIO(content)
        return request

    def test_init__(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        self.assertIs(sentinel.status_worker, resource.worker)
        self.assertTrue(resource.isLeaf)
        self.assertEqual([b"POST"], resource.allowedMethods)
        self.assertEqual(
            ["event_type", "origin", "name", "description"],
            resource.requiredMessageKeys,
        )

    def test_render_POST_missing_authorization(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        request = DummyRequest([])
        output = resource.render_POST(request)
        self.assertEqual(b"", output)
        self.assertEqual(401, request.responseCode)

    def test_render_POST_empty_authorization(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        request = DummyRequest([])
        request.requestHeaders.addRawHeader(b"authorization", "")
        output = resource.render_POST(request)
        self.assertEqual(b"", output)
        self.assertEqual(401, request.responseCode)

    def test_render_POST_bad_authorization(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        request = DummyRequest([])
        request.requestHeaders.addRawHeader(
            b"authorization", factory.make_name("auth")
        )
        output = resource.render_POST(request)
        self.assertEqual(b"", output)
        self.assertEqual(401, request.responseCode)

    def test_render_POST_body_must_be_ascii(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        request = self.make_request(content=b"\xe9")
        output = resource.render_POST(request)
        self.assertEqual(
            b"Status payload must be ASCII-only: 'ascii' codec can't "
            b"decode byte 0xe9 in position 0: ordinal not in range(128)",
            output,
        )
        self.assertEqual(400, request.responseCode)

    def test_render_POST_body_must_be_valid_json(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        request = self.make_request(content=b"testing not json")
        output = resource.render_POST(request)
        self.assertEqual(
            b"Status payload is not valid JSON:\ntesting not json\n\n", output
        )
        self.assertEqual(400, request.responseCode)

    def test_render_POST_validates_required_keys(self):
        resource = StatusHandlerResource(sentinel.status_worker)
        request = self.make_request(content=json.dumps({}).encode("ascii"))
        output = resource.render_POST(request)
        self.assertEqual(
            b"Missing parameter(s) event_type, origin, name, description "
            b"in status message.",
            output,
        )
        self.assertEqual(400, request.responseCode)

    def test_render_POST_queue_messages(self):
        status_worker = Mock()
        status_worker.queueMessage = Mock()
        status_worker.queueMessage.return_value = succeed(None)
        resource = StatusHandlerResource(status_worker)
        message = {
            "event_type": (
                factory.make_name("type") + "/" + factory.make_name("sub_type")
            ),
            "origin": factory.make_name("origin"),
            "name": factory.make_name("name"),
            "description": factory.make_name("description"),
        }
        token = factory.make_name("token")
        request = self.make_request(
            content=json.dumps(message).encode("ascii"), token=token
        )
        output = resource.render_POST(request)
        self.assertEqual(NOT_DONE_YET, output)
        self.assertEqual(204, request.responseCode)
        status_worker.queueMessage.assert_called_once_with(token, message)


class TestStatusWorkerServiceTransactional(MAASTransactionServerTestCase):
    assertRaises = TestCase.assertRaises

    def setUp(self):
        super().setUp()
        self.patch(node_module, "stop_workflow")

    @transactional
    def make_nodes_with_tokens(self):
        nodes = [factory.make_Node() for _ in range(3)]
        return [
            (node, NodeKey.objects.get_token_for_node(node)) for node in nodes
        ]

    def make_message(self):
        return {
            "event_type": factory.make_name("type"),
            "origin": factory.make_name("origin"),
            "name": factory.make_name("name"),
            "description": factory.make_name("description"),
            "timestamp": datetime.now(timezone.utc).timestamp(),
        }

    def test_init__(self):
        worker = StatusWorkerService(sentinel.dbtasks, clock=sentinel.reactor)
        self.assertEqual(sentinel.dbtasks, worker.dbtasks)
        self.assertEqual(sentinel.reactor, worker.clock)
        self.assertEqual(60, worker.step)
        self.assertEqual((worker._tryUpdateNodes, tuple(), {}), worker.call)

    def test_tryUpdateNodes_returns_None_when_empty_queue(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        self.assertIsNone(worker._tryUpdateNodes())

    @wait_for_reactor
    @inlineCallbacks
    def test_tryUpdateNodes_sends_work_to_dbtasks(self):
        nodes_with_tokens = yield deferToDatabase(self.make_nodes_with_tokens)
        node_messages = {
            node: [self.make_message() for _ in range(3)]
            for node, _ in nodes_with_tokens
        }
        dbtasks = Mock()
        worker = StatusWorkerService(dbtasks)
        for node, token in nodes_with_tokens:
            for message in node_messages[node]:
                worker.queueMessage(token.key, message)
        yield worker._tryUpdateNodes()
        dbtasks.addTask.assert_has_calls(
            [
                call(worker._processMessages, node, messages)
                for node, messages in node_messages.items()
            ]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_processMessages_fails_when_in_transaction(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        with self.assertRaises(TransactionManagementError):
            yield deferToDatabase(
                transactional(worker._processMessages),
                sentinel.node,
                [sentinel.message],
            )

    @wait_for_reactor
    @inlineCallbacks
    def test_processMessageNow_fails_when_in_transaction(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        with self.assertRaises(TransactionManagementError):
            yield deferToDatabase(
                transactional(worker._processMessageNow),
                sentinel.node,
                sentinel.message,
            )

    @wait_for_reactor
    @inlineCallbacks
    def test_processMessages_doesnt_call_when_node_deleted(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        mock_processMessage = self.patch(worker, "_processMessage")
        mock_processMessage.return_value = False
        yield deferToDatabase(
            worker._processMessages,
            sentinel.node,
            [sentinel.message1, sentinel.message2],
        )
        mock_processMessage.assert_called_once_with(
            sentinel.node, sentinel.message1
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_processMessages_calls_processMessage(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        mock_processMessage = self.patch(worker, "_processMessage")
        mock_processMessage.return_value = True
        yield deferToDatabase(
            worker._processMessages,
            sentinel.node,
            [sentinel.message1, sentinel.message2],
        )
        mock_processMessage.assert_has_calls(
            [
                call(sentinel.node, sentinel.message1),
                call(sentinel.node, sentinel.message2),
            ]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_queueMessages_processes_top_level_message_instantly(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        mock_processMessage = self.patch(worker, "_processMessage")
        message = self.make_message()
        message["event_type"] = "finish"
        nodes_with_tokens = yield deferToDatabase(self.make_nodes_with_tokens)
        node, token = nodes_with_tokens[0]
        yield worker.queueMessage(token.key, message)
        mock_processMessage.assert_called_once_with(node, message)

    @wait_for_reactor
    @inlineCallbacks
    def test_queueMessages_processes_top_level_status_messages_instantly(self):
        for name in EVENT_STATUS_MESSAGES.keys():
            worker = StatusWorkerService(sentinel.dbtasks)
            mock_processMessage = self.patch(worker, "_processMessage")
            message = self.make_message()
            message["event_type"] = "start"
            message["name"] = name
            nodes_with_tokens = yield deferToDatabase(
                self.make_nodes_with_tokens
            )
            node, token = nodes_with_tokens[0]
            yield worker.queueMessage(token.key, message)
            mock_processMessage.assert_called_once_with(node, message)

    @wait_for_reactor
    @inlineCallbacks
    def test_queueMessages_processes_files_message_instantly(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        mock_processMessage = self.patch(worker, "_processMessage")
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(bz2.compress(contents))
        message = self.make_message()
        message["files"] = [
            {
                "path": "sample.txt",
                "encoding": "uuencode",
                "compression": "bzip2",
                "content": encoded_content,
            }
        ]
        nodes_with_tokens = yield deferToDatabase(self.make_nodes_with_tokens)
        node, token = nodes_with_tokens[0]
        yield worker.queueMessage(token.key, message)
        mock_processMessage.assert_called_once_with(node, message)

    @wait_for_reactor
    @inlineCallbacks
    def test_queueMessages_handled_invalid_nodekey_with_instant_msg(self):
        worker = StatusWorkerService(sentinel.dbtasks)
        mock_processMessage = self.patch(worker, "_processMessage")
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(bz2.compress(contents))
        message = self.make_message()
        message["files"] = [
            {
                "path": "sample.txt",
                "encoding": "uuencode",
                "compression": "bzip2",
                "content": encoded_content,
            }
        ]
        nodes_with_tokens = yield deferToDatabase(self.make_nodes_with_tokens)
        node, token = nodes_with_tokens[0]
        yield deferToDatabase(token.delete)
        yield worker.queueMessage(token.key, message)
        mock_processMessage.assert_not_called()


def encode_as_base64(content):
    return base64.encodebytes(content).decode("ascii")


class TestStatusWorkerService(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.useFixture(SignalsDisabled("power"))
        self.patch(api_twisted_module, "signal_workflow")
        self.patch(node_module, "stop_workflow")

    def processMessage(self, node, payload):
        worker = StatusWorkerService(sentinel.dbtasks)
        return worker._processMessage(node, payload)

    def test_process_message_logs_event_for_start_event_type(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        payload = {
            "event_type": "start",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Installation has started.",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        event = Event.objects.last()
        self.assertEqual(
            event.description,
            CURTIN_INSTALL_LOG + " changed status from 'Pending' to 'Running'",
        )

    def test_process_message_returns_false_when_node_deleted(self):
        node1 = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        node1.delete()
        payload = {
            "event_type": "finish",
            "result": "SUCCESS",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
        }
        self.assertFalse(self.processMessage(node1, payload))

    def test_status_installation_result_does_not_affect_other_node(self):
        node1 = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        node2 = factory.make_Node(status=NODE_STATUS.DEPLOYING)
        script = factory.make_Script(may_reboot=True)
        factory.make_ScriptResult(
            script=script,
            script_set=node1.current_installation_script_set,
            status=SCRIPT_STATUS.RUNNING,
        )
        payload = {
            "event_type": "start",
            "result": "SUCCESS",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node1, payload)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node2).status)
        # Check last node1 event.
        self.assertEqual(
            CURTIN_INSTALL_LOG + " changed status from 'Pending' to 'Running'",
            Event.objects.filter(node=node1).last().description,
        )
        # There must be no events for node2.
        self.assertFalse(Event.objects.filter(node=node2).exists())

    def test_status_installation_success_leaves_node_deploying(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            with_empty_script_sets=True,
        )
        script = factory.make_Script(may_reboot=True)
        factory.make_ScriptResult(
            script=script,
            script_set=node.current_installation_script_set,
            status=SCRIPT_STATUS.RUNNING,
        )
        payload = {
            "event_type": "start",
            "result": "SUCCESS",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(NODE_STATUS.DEPLOYING, reload_object(node).status)
        # Check last node event.
        self.assertEqual(
            "/tmp/install.log changed status from 'Pending' to 'Running'",
            Event.objects.filter(node=node).last().description,
        )

    def test_status_commissioning_failure_leaves_node_failed(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )
        # Check last node event.
        self.assertEqual(
            [
                "'curtin' Commissioning",
                "Commissioning failed, cloud-init reported a failure (refer "
                "to the event log for more information)",
            ],
            [e.description for e in Event.objects.filter(node=node)],
        )

    def test_status_commissioning_failure_clears_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING, owner=user
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )
        self.assertIsNone(reload_object(node).owner)

    def test_status_commissioning_failure_aborts_scripts(self):
        # Regression test for LP:1732948
        user = factory.make_User()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            owner=user,
            with_empty_script_sets=True,
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )
        for script_result in node.get_latest_script_results:
            self.assertEqual(SCRIPT_STATUS.ABORTED, script_result.status)

    def test_status_commissioning_failure_ignored_when_rebooting_running(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            owner=user,
            with_empty_script_sets=True,
        )
        script = factory.make_Script(may_reboot=True)
        script_result = factory.make_ScriptResult(
            script=script,
            script_set=node.current_commissioning_script_set,
            status=SCRIPT_STATUS.RUNNING,
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        self.processMessage(node, payload)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)
        self.assertEqual(
            SCRIPT_STATUS.RUNNING, reload_object(script_result).status
        )

    def test_status_commissioning_failure_ignored_when_rebooting_passed(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            owner=user,
            with_empty_script_sets=True,
        )
        script = factory.make_Script(may_reboot=True)
        now = datetime.now(timezone.utc)
        script_result = factory.make_ScriptResult(
            script=script,
            script_set=node.current_commissioning_script_set,
            status=SCRIPT_STATUS.PASSED,
            started=now - timedelta(seconds=120),
            ended=now - timedelta(seconds=10),
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(NODE_STATUS.COMMISSIONING, reload_object(node).status)
        self.assertEqual(
            SCRIPT_STATUS.PASSED, reload_object(script_result).status
        )

    def test_status_installation_failure_leaves_node_failed(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status
        )
        # Check last node event.
        self.assertEqual(
            "Installation failed (refer to the installation"
            " log for more information).",
            Event.objects.filter(node=node).last().description,
        )

    def test_status_ok_for_modules_final_triggers_kvm_install(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        payload = {
            "event_type": "finish",
            "result": "OK",
            "origin": "cloud-init",
            "name": "modules-final",
            "description": "America for Make Benefit Glorious Nation",
            "timestamp": datetime.now(timezone.utc),
        }
        mock_create_vmhost = self.patch(
            api_twisted_module, "_create_vmhost_for_deployment"
        )
        self.processMessage(node, payload)
        mock_create_vmhost.assert_called_once_with(node)

    def test_status_ok_for_modules_final_triggers_register_vmhost(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            register_vmhost=True,
        )
        payload = {
            "event_type": "finish",
            "result": "OK",
            "origin": "cloud-init",
            "name": "modules-final",
            "description": "America for Make Benefit Glorious Nation",
            "timestamp": datetime.now(timezone.utc),
        }
        mock_create_vmhost = self.patch(
            api_twisted_module, "_create_vmhost_for_deployment"
        )
        self.processMessage(node, payload)
        mock_create_vmhost.assert_called_once_with(node)

    def test_status_installation_fail_leaves_node_failed(self):
        node = factory.make_Node(interface=True, status=NODE_STATUS.DEPLOYING)
        payload = {
            "event_type": "finish",
            "result": "FAIL",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status
        )
        # Check last node event.
        self.assertEqual(
            "Installation failed (refer to the installation"
            " log for more information).",
            Event.objects.filter(node=node).last().description,
        )

    def test_status_installation_failure_doesnt_clear_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYING, owner=user
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
        }
        self.assertEqual(user, node.owner)  # Node has an owner
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_DEPLOYMENT, reload_object(node).status
        )
        self.assertIsNotNone(reload_object(node).owner)

    def test_status_installation_failure_fails_script_result(self):
        # Regression test for LP:1701352
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYING, owner=user
        )
        node.current_installation_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.INSTALLATION
        )
        node.save()
        script_result = factory.make_ScriptResult(
            script_set=node.current_installation_script_set,
            script_name=CURTIN_INSTALL_LOG,
            status=SCRIPT_STATUS.RUNNING,
        )
        content = factory.make_bytes()
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": CURTIN_INSTALL_LOG,
                    "encoding": "base64",
                    "content": encode_as_base64(content),
                }
            ],
        }
        self.processMessage(node, payload)
        self.assertEqual(
            SCRIPT_STATUS.FAILED, reload_object(script_result).status
        )

    def test_status_POST_files_none_are_ignored(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DEPLOYING, owner=user
        )
        node.current_installation_script_set = factory.make_ScriptSet(
            node=node, result_type=RESULT_TYPE.INSTALLATION
        )
        node.save()
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Command Install",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": CURTIN_INSTALL_LOG,
                    "encoding": "base64",
                    "content": None,
                }
            ],
        }
        self.processMessage(node, payload)
        self.assertEqual(0, len(list(node.current_installation_script_set)))

    def test_status_commissioning_failure_does_not_populate_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_COMMISSIONING, reload_object(node).status
        )
        populate_tags_for_single_node.assert_not_called()

    def test_status_erasure_failure_leaves_node_failed(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DISK_ERASING
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-erase",
            "description": "Erasing disk",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status
        )
        # Check last node event.
        self.assertEqual(
            "Failed to erase disks.",
            Event.objects.filter(node=node).last().description,
        )

    def test_status_erasure_failure_does_not_populate_tags(self):
        populate_tags_for_single_node = self.patch(
            api, "populate_tags_for_single_node"
        )
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DISK_ERASING
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-erase",
            "description": "Erasing disk",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status
        )
        populate_tags_for_single_node.assert_not_called()

    def test_status_erasure_failure_doesnt_clear_owner(self):
        user = factory.make_User()
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.DISK_ERASING, owner=user
        )
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "cmd-erase",
            "description": "Erasing disk",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        self.assertEqual(
            NODE_STATUS.FAILED_DISK_ERASING, reload_object(node).status
        )
        self.assertEqual(user, node.owner)

    def test_status_with_file_bad_encoder_fails(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(bz2.compress(contents))
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": "sample.txt",
                    "encoding": "uuencode",
                    "compression": "bzip2",
                    "content": encoded_content,
                }
            ],
        }
        self.assertRaises(ValueError, self.processMessage, node, payload)

    def test_status_with_file_bad_compression_fails(self):
        node = factory.make_Node(
            interface=True, status=NODE_STATUS.COMMISSIONING
        )
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(bz2.compress(contents))
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": "sample.txt",
                    "encoding": "base64",
                    "compression": "jpeg",
                    "content": encoded_content,
                }
            ],
        }
        self.assertRaises(ValueError, self.processMessage, node, payload)

    def test_status_with_file_no_compression_succeeds(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(contents)
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": script_result.name,
                    "encoding": "base64",
                    "content": encoded_content,
                }
            ],
        }
        self.processMessage(node, payload)
        self.assertEqual(contents, reload_object(script_result).output)

    def test_status_with_file_invalid_statuses_fails(self):
        """Adding files should fail for every status that's neither
        COMMISSIONING nor DEPLOYING"""
        for node_status in [
            NODE_STATUS.DEFAULT,
            NODE_STATUS.NEW,
            NODE_STATUS.MISSING,
            NODE_STATUS.READY,
            NODE_STATUS.RESERVED,
            NODE_STATUS.RETIRED,
            NODE_STATUS.BROKEN,
            NODE_STATUS.ALLOCATED,
            NODE_STATUS.RELEASING,
            NODE_STATUS.FAILED_RELEASING,
            NODE_STATUS.DISK_ERASING,
            NODE_STATUS.FAILED_DISK_ERASING,
        ]:
            node = factory.make_Node(interface=True, status=node_status)
            contents = b"These are the contents of the file."
            encoded_content = encode_as_base64(bz2.compress(contents))
            payload = {
                "event_type": "finish",
                "result": "FAILURE",
                "origin": "curtin",
                "name": "commissioning",
                "description": "Commissioning",
                "timestamp": datetime.now(timezone.utc),
                "files": [
                    {
                        "path": "sample.txt",
                        "encoding": "base64",
                        "compression": "bzip2",
                        "content": encoded_content,
                    }
                ],
            }
            self.assertRaises(ValueError, self.processMessage, node, payload)

    def test_status_with_file_succeeds(self):
        """Adding files should succeed for every status that's either
        COMMISSIONING or DEPLOYING"""
        for node_status, target_status in [
            (NODE_STATUS.COMMISSIONING, NODE_STATUS.FAILED_COMMISSIONING),
            (NODE_STATUS.DEPLOYING, NODE_STATUS.FAILED_DEPLOYMENT),
        ]:
            node = factory.make_Node(
                interface=True, status=node_status, with_empty_script_sets=True
            )
            if node_status == NODE_STATUS.COMMISSIONING:
                script_set = node.current_commissioning_script_set
            elif node_status == NODE_STATUS.DEPLOYING:
                script_set = node.current_installation_script_set
            script_result = script_set.scriptresult_set.first()
            script_result.status = SCRIPT_STATUS.RUNNING
            script_result.save()
            contents = b"These are the contents of the file."
            encoded_content = encode_as_base64(bz2.compress(contents))
            payload = {
                "event_type": "finish",
                "result": "FAILURE",
                "origin": "curtin",
                "name": "commissioning",
                "description": "Commissioning",
                "timestamp": datetime.now(timezone.utc),
                "files": [
                    {
                        "path": script_result.name,
                        "encoding": "base64",
                        "compression": "bzip2",
                        "content": encoded_content,
                    }
                ],
            }
            self.processMessage(node, payload)
            self.assertEqual(target_status, reload_object(node).status)
            # Check the node result.
            self.assertEqual(contents, reload_object(script_result).output)

    def test_status_with_results_succeeds(self):
        """Adding a script result should succeed"""
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(bz2.compress(contents))
        payload = {
            "event_type": "finish",
            "result": "FAILURE",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": script_result.name,
                    "encoding": "base64",
                    "compression": "bzip2",
                    "content": encoded_content,
                    "result": -42,
                }
            ],
        }
        self.processMessage(node, payload)
        script_result = reload_object(script_result)
        self.assertEqual(contents, script_result.output)
        self.assertEqual(-42, script_result.exit_status)

    def test_status_with_results_no_exit_status_defaults_to_zero(self):
        """Adding a script result should succeed without a return code defaults
        it to zero when passing."""
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.COMMISSIONING,
            with_empty_script_sets=True,
        )
        script_result = (
            node.current_commissioning_script_set.scriptresult_set.first()
        )
        script_result.status = SCRIPT_STATUS.RUNNING
        script_result.save()
        contents = b"These are the contents of the file."
        encoded_content = encode_as_base64(bz2.compress(contents))
        payload = {
            "event_type": "finish",
            "result": "OK",
            "origin": "curtin",
            "name": "commissioning",
            "description": "Commissioning",
            "timestamp": datetime.now(timezone.utc),
            "files": [
                {
                    "path": script_result.name,
                    "encoding": "base64",
                    "compression": "bzip2",
                    "content": encoded_content,
                }
            ],
        }
        self.processMessage(node, payload)
        self.assertEqual(0, reload_object(script_result).exit_status)

    def test_captures_installation_start(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING, with_empty_script_sets=True
        )
        payload = {
            "event_type": "start",
            "origin": "curtin",
            "name": "cmd-install",
            "description": "Installation has started.",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        script_set = node.current_installation_script_set
        script_result = script_set.find_script_result(
            script_name=CURTIN_INSTALL_LOG
        )
        self.assertEqual(SCRIPT_STATUS.RUNNING, script_result.status)

    def test_resets_status_expires(self):
        node = factory.make_Node(
            status=NODE_STATUS.DEPLOYING,
            status_expires=factory.make_date(),
            with_empty_script_sets=True,
        )
        payload = {
            "event_type": random.choice(["start", "finish"]),
            "origin": "curtin",
            "name": random.choice(
                [
                    "cmd-install",
                    "cmd-install/stage-early",
                    "cmd-install/stage-late",
                ]
            ),
            "description": "Installing",
            "timestamp": datetime.now(timezone.utc),
        }
        self.processMessage(node, payload)
        node = reload_object(node)
        # Testing for the exact time will fail during testing due to now()
        # being different in reset_status_expires vs here. Pad by 1 minute
        # to make sure its reset but won't fail testing.
        expected_time = now() + timedelta(
            minutes=get_node_timeout(NODE_STATUS.DEPLOYING)
        )
        self.assertGreaterEqual(
            node.status_expires, expected_time - timedelta(minutes=1)
        )
        self.assertLessEqual(
            node.status_expires, expected_time + timedelta(minutes=1)
        )

    def test_disk_erasing_machine_failed(self):
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING,
            status_expires=factory.make_date(),
            with_empty_script_sets=True,
        )
        release_node_patch = self.patch(Node, "release")
        payload = {
            "name": "modules-final",
            "description": "running modules for final",
            "event_type": "finish",
            "origin": "cloudinit",
            "timestamp": datetime.now(timezone.utc),
            "result": "FAILURE",
        }
        self.processMessage(node, payload)
        node = reload_object(node)
        self.assertEqual(node.status, NODE_STATUS.FAILED_DISK_ERASING)
        release_node_patch.assert_not_called()

    def test_disk_erasing_machine_transitioned_to_ready_with_modules_final_event(
        self,
    ):
        node = factory.make_Node(
            status=NODE_STATUS.DISK_ERASING,
            status_expires=factory.make_date(),
            with_empty_script_sets=True,
        )
        release_node_patch = self.patch(Node, "release")
        payload = {
            "name": "modules-final",
            "description": "running modules for final",
            "event_type": "finish",
            "origin": "cloudinit",
            "timestamp": datetime.now(timezone.utc),
            "result": "SUCCESS",
        }
        self.processMessage(node, payload)
        # Testing for the exact time will fail during testing due to now()
        # being different in reset_status_expires vs here. Pad by 1 minute
        # to make sure its reset but won't fail testing.
        release_node_patch.assert_called_once()

    def test_releasing_machine_failed(self):
        node = factory.make_Node(
            status=NODE_STATUS.RELEASING,
            status_expires=factory.make_date(),
            with_empty_script_sets=True,
        )
        release_node_patch = self.patch(Node, "release")
        payload = {
            "name": "modules-final",
            "description": "running modules for final",
            "event_type": "finish",
            "origin": "cloudinit",
            "timestamp": datetime.now(timezone.utc),
            "result": "FAILURE",
        }
        self.processMessage(node, payload)
        node = reload_object(node)
        self.assertEqual(node.status, NODE_STATUS.FAILED_RELEASING)
        release_node_patch.assert_not_called()

    def test_releasing_machine_transitioned_to_ready_with_modules_final_event(
        self,
    ):
        node = factory.make_Node(
            status=NODE_STATUS.RELEASING,
            status_expires=factory.make_date(),
            with_empty_script_sets=True,
        )
        release_node_patch = self.patch(Node, "release")
        payload = {
            "name": "modules-final",
            "description": "running modules for final",
            "event_type": "finish",
            "origin": "cloudinit",
            "timestamp": datetime.now(timezone.utc),
            "result": "SUCCESS",
        }
        self.processMessage(node, payload)
        release_node_patch.assert_called_once()


class TestCreateVMHostForDeployment(MAASServerTestCase):
    def setUp(self):
        super().setUp()
        self.patch(node_module, "stop_workflow")
        self.mock_discover_and_sync = self.patch(
            api_twisted_module, "discover_and_sync_vmhost"
        )

    def test_marks_failed_if_no_creds_install_kvm(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.FAILED_DEPLOYMENT)
        self.assertEqual(
            node.error_description,
            "Failed to deploy VM host: Credentials not found.",
        )

    def test_marks_failed_if_no_password_register_vmhost(self):
        node = factory.make_Node(
            interface=True,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            register_vmhost=True,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.FAILED_DEPLOYMENT)
        self.assertEqual(
            node.error_description,
            "Failed to deploy VM host: Credentials not found.",
        )

    def test_creates_vmhost_register_vmhost(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            register_vmhost=True,
        )
        factory.make_StaticIPAddress(interface=node.boot_interface)
        cert = get_sample_cert()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "deploy-metadata",
            {
                "lxd-certificate": cert.certificate_pem()
                + cert.private_key_pem()
            },
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        lxd_vmhost = Pod.objects.get(power_type="lxd")
        self.mock_discover_and_sync.assert_called_once_with(lxd_vmhost, user)
        self.assertIsNone(
            secret_manager.get_composite_secret(
                "deploy-metadata", obj=node, default=None
            )
        )

    def test_creates_vmhost_install_kvm(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        factory.make_StaticIPAddress(interface=node.boot_interface)
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "deploy-metadata",
            {"virsh-password": "xyz123"},
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        virsh_vmhost = Pod.objects.get(power_type="virsh")
        self.mock_discover_and_sync.assert_called_once_with(virsh_vmhost, user)
        self.assertIsNone(
            secret_manager.get_composite_secret(
                "deploy-metadata", obj=node, default=None
            )
        )

    def test_creates_vmhost_both(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
            register_vmhost=True,
        )
        factory.make_StaticIPAddress(interface=node.boot_interface)
        cert = get_sample_cert()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "deploy-metadata",
            {
                "lxd-certificate": cert.certificate_pem()
                + cert.private_key_pem(),
                "virsh-password": "xyz123",
            },
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        virsh_vmhost = Pod.objects.get(power_type="virsh")
        lxd_vmhost = Pod.objects.get(power_type="lxd")
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        self.mock_discover_and_sync.assert_has_calls(
            [
                call(virsh_vmhost, user),
                call(lxd_vmhost, user),
            ],
            any_order=True,
        )
        self.assertIsNone(
            secret_manager.get_composite_secret(
                "deploy-metadata", obj=node, default=None
            )
        )

    def test_creates_vmhost_prefer_not_discovered_addresses(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
            register_vmhost=True,
        )
        factory.make_StaticIPAddress(
            interface=node.boot_interface,
            alloc_type=IPADDRESS_TYPE.DISCOVERED,
        )
        ip = factory.make_StaticIPAddress(
            interface=node.boot_interface,
            alloc_type=IPADDRESS_TYPE.AUTO,
        )
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "deploy-metadata",
            {
                "virsh-password": "xyz123",
            },
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        vmhost = Pod.objects.get(power_type="virsh")
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        addr = ip.ip
        if IPAddress(addr).version == 6:
            addr = f"[{addr}]"
        self.assertEqual(
            vmhost.power_parameters.get("power_address"),
            f"qemu+ssh://virsh@{addr}/system",
        )

    def test_creates_vmhost_pick_right_interface_address(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        # deploying a machine as a VM host bridges the boot interface
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE,
            node=node,
            parents=[node.boot_interface],
        )
        ip = factory.make_StaticIPAddress(interface=bridge)
        another_if = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(interface=another_if)
        SecretManager().set_composite_secret(
            "deploy-metadata",
            {"virsh-password": "xyz123"},
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        virsh_vmhost = Pod.objects.get(power_type="virsh")

        addr = ip.ip
        if IPAddress(addr).version == 6:
            addr = f"[{addr}]"
        self.assertEqual(
            virsh_vmhost.power_parameters.get("power_address"),
            f"qemu+ssh://virsh@{addr}/system",
        )

    def test_creates_vmhost_pick_right_interface_with_bond(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        iface = factory.make_Interface(node=node)
        bond = factory.make_Interface(
            iftype=INTERFACE_TYPE.BOND,
            node=node,
            parents=[node.get_boot_interface(), iface],
        )
        # deploying a machine as a VM host bridges the boot interface, which is
        # now the bond
        bridge = factory.make_Interface(
            iftype=INTERFACE_TYPE.BRIDGE,
            node=node,
            parents=[bond],
        )
        ip = factory.make_StaticIPAddress(interface=bridge)
        another_if = factory.make_Interface(INTERFACE_TYPE.PHYSICAL, node=node)
        factory.make_StaticIPAddress(interface=another_if)
        SecretManager().set_composite_secret(
            "deploy-metadata",
            {"virsh-password": "xyz123"},
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        virsh_vmhost = Pod.objects.get(power_type="virsh")

        addr = ip.ip
        if IPAddress(addr).version == 6:
            addr = f"[{addr}]"
        self.assertEqual(
            virsh_vmhost.power_parameters.get("power_address"),
            f"qemu+ssh://virsh@{addr}/system",
        )

    def test_marks_failed_if_form_invalid(self):
        mock_form = self.patch(api_twisted_module, "PodForm").return_value
        mock_form.is_valid.return_value = False
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        factory.make_StaticIPAddress(interface=node.boot_interface)
        SecretManager().set_composite_secret(
            "deploy-metadata",
            {"virsh-password": "xyz123"},
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.FAILED_DEPLOYMENT)
        self.assertEqual(node.error_description, POD_CREATION_ERROR)

    def test_marks_failed_if_form_save_raises(self):
        mock_form = self.patch(api_twisted_module, "PodForm").return_value
        mock_form.is_valid.return_value = True
        mock_form.save.side_effect = ValueError
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        factory.make_StaticIPAddress(interface=node.boot_interface)
        SecretManager().set_composite_secret(
            "deploy-metadata",
            {"virsh-password": "xyz123"},
            obj=node,
        )
        _create_vmhost_for_deployment(node)
        self.assertEqual(node.status, NODE_STATUS.FAILED_DEPLOYMENT)
        self.assertEqual(node.error_description, POD_CREATION_ERROR)

    def test_marks_failed_if_form_save_raises_database_error(self):
        mock_form = self.patch(api_twisted_module, "PodForm").return_value
        mock_form.is_valid.return_value = True
        mock_form.save.side_effect = DatabaseError("broken transaction")
        node = factory.make_Node_with_Interface_on_Subnet(
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        factory.make_StaticIPAddress(interface=node.boot_interface)
        SecretManager().set_composite_secret(
            "deploy-metadata",
            {"virsh-password": "xyz123"},
            obj=node,
        )
        self.assertRaises(DatabaseError, _create_vmhost_for_deployment, node)

    def test_ignore_unused_lxd_creds(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            install_kvm=True,
        )
        ip = factory.make_StaticIPAddress(interface=node.boot_interface)
        cert = get_sample_cert()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "deploy-metadata",
            {
                "lxd-certificate": cert.certificate_pem()
                + cert.private_key_pem(),
                "virsh-password": "xyz123",
            },
            obj=node,
        )
        addr = ip.ip
        if IPAddress(addr).version == 6:
            addr = f"[{addr}]"
        _create_vmhost_for_deployment(node)
        virsh_vmhost = Pod.objects.get(power_type="virsh")
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        self.mock_discover_and_sync.assert_has_calls(
            [
                call(virsh_vmhost, user),
            ],
            any_order=True,
        )
        self.assertIsNone(
            secret_manager.get_composite_secret(
                "deploy-metadata", obj=node, default=None
            )
        )

    def test_ignore_unused_virsh_creds(self):
        user = factory.make_User()
        node = factory.make_Node_with_Interface_on_Subnet(
            owner=user,
            status=NODE_STATUS.DEPLOYING,
            agent_name="maas-kvm-pod",
            register_vmhost=True,
        )
        ip = factory.make_StaticIPAddress(interface=node.boot_interface)
        cert = get_sample_cert()
        secret_manager = SecretManager()
        secret_manager.set_composite_secret(
            "deploy-metadata",
            {
                "lxd-certificate": cert.certificate_pem()
                + cert.private_key_pem(),
                "virsh-password": "xyz123",
            },
            obj=node,
        )
        addr = ip.ip
        if IPAddress(addr).version == 6:
            addr = f"[{addr}]"
        _create_vmhost_for_deployment(node)
        lxd_vmhost = Pod.objects.get(power_type="lxd")
        self.assertEqual(node.status, NODE_STATUS.DEPLOYED)
        self.mock_discover_and_sync.assert_has_calls(
            [
                call(lxd_vmhost, user),
            ],
            any_order=True,
        )
        self.assertIsNone(
            secret_manager.get_composite_secret(
                "deploy-metadata", obj=node, default=None
            )
        )
