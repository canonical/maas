# Copyright 2015-2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import deque
from datetime import datetime, timedelta
import json
import random
from unittest.mock import MagicMock, sentinel

from django.core.exceptions import ValidationError
from django.http import HttpRequest
from twisted.internet import defer
from twisted.internet.defer import fail, inlineCallbacks, succeed
from twisted.web.server import NOT_DONE_YET

from apiclient.utils import ascii_url
from maasserver.eventloop import services
from maasserver.testing.factory import factory as maas_factory
from maasserver.testing.listener import FakePostgresListenerService
from maasserver.testing.testcase import MAASTransactionServerTestCase
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets import protocol as protocol_module
from maasserver.websockets.base import Handler
from maasserver.websockets.handlers import DeviceHandler, MachineHandler
from maasserver.websockets.protocol import (
    MSG_TYPE,
    RESPONSE_TYPE,
    WebSocketFactory,
    WebSocketProtocol,
)
from maasserver.websockets.websockets import STATUSES
from maastesting.crochet import wait_for
from maastesting.factory import factory as maastesting_factory
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.refresh.node_info_scripts import LSHW_OUTPUT_NAME
from provisioningserver.utils.twisted import synchronous
from provisioningserver.utils.url import splithost

wait_for_reactor = wait_for()


class TestWebSocketProtocol(MAASTransactionServerTestCase):
    def make_protocol(self, patch_authenticate=True, transport_uri=""):
        listener = FakePostgresListenerService()
        factory = WebSocketFactory(listener)
        self.patch(factory, "registerRPCEvents")
        self.patch(factory, "unregisterRPCEvents")
        factory.startFactory()
        self.addCleanup(factory.stopFactory)
        protocol = factory.buildProtocol(None)
        protocol.transport = MagicMock()
        protocol.transport.cookies = b""
        protocol.transport.uri = transport_uri
        protocol.transport.host = random.choice(
            [
                maastesting_factory.make_ipv4_address()
                + ":%d" % maastesting_factory.pick_port(),
                "["
                + maastesting_factory.make_ipv6_address()
                + "]:%d" % maastesting_factory.pick_port(),
            ]
        )
        protocol.request = HttpRequest()
        protocol.session = MagicMock()
        protocol.session.session_key = ""
        if patch_authenticate:
            self.patch(protocol, "authenticate")
        return protocol, factory

    def make_ws_uri(self, csrftoken=None):
        """Make a websocket URI.

        In practice, the URI usually looks like:
        '/MAAS/ws?csrftoken=<csrftoken>' but in practice the code only
        cares about the presence of the CSRF token in the query string.
        """
        url = "/{}/{}".format(
            maas_factory.make_name("path"),
            maas_factory.make_name("path"),
        )
        if csrftoken is not None:
            url += "?csrftoken=%s" % csrftoken
        return ascii_url(url)

    def get_written_transport_message(self, protocol):
        call = protocol.transport.write.call_args_list.pop()
        return json.loads(call[0][0].decode("ascii"))

    def test_connectionMade_sets_the_request(self):
        protocol, _ = self.make_protocol(patch_authenticate=False)
        self.patch_autospec(protocol, "authenticate")
        # Be sure the request field is populated by the time that
        # processMessages() is called.
        processMessages_mock = self.patch_autospec(protocol, "processMessages")
        processMessages_mock.side_effect = lambda: self.assertEqual(
            protocol.user, protocol.request.user
        )
        protocol.authenticate.return_value = defer.succeed(sentinel.user)
        protocol.connectionMade()
        self.addCleanup(protocol.connectionLost, "")
        self.assertEqual(protocol.user, protocol.request.user)
        self.assertEqual(
            protocol.request.META["HTTP_USER_AGENT"],
            protocol.transport.user_agent,
        )
        self.assertEqual(
            protocol.request.META["REMOTE_ADDR"], protocol.transport.ip_address
        )
        self.assertEqual(
            protocol.request.META["SERVER_NAME"],
            splithost(protocol.transport.host)[0],
        )
        self.assertEqual(
            protocol.request.META["SERVER_PORT"],
            splithost(protocol.transport.host)[1],
        )

    def test_connectionMade_sets_the_request_default_server_name_port(self):
        protocol, _ = self.make_protocol(patch_authenticate=False)
        self.patch_autospec(protocol, "authenticate")
        self.patch_autospec(protocol, "processMessages")
        mock_splithost = self.patch_autospec(protocol_module, "splithost")
        mock_splithost.return_value = (None, None)
        protocol.authenticate.return_value = defer.succeed(sentinel.user)
        protocol.connectionMade()
        self.addCleanup(protocol.connectionLost, "")
        self.assertEqual(protocol.request.META["SERVER_NAME"], "localhost")
        self.assertEqual(protocol.request.META["SERVER_PORT"], 5248)

    def test_connectionMade_processes_messages(self):
        protocol, _ = self.make_protocol(patch_authenticate=False)
        self.patch_autospec(protocol, "authenticate")
        self.patch_autospec(protocol, "processMessages")
        protocol.authenticate.return_value = defer.succeed(True)
        protocol.connectionMade()
        self.addCleanup(protocol.connectionLost, "")
        protocol.processMessages.assert_called_once_with()

    def test_connectionMade_adds_self_to_factory_if_auth_succeeds(self):
        protocol, factory = self.make_protocol()
        mock_authenticate = self.patch(protocol, "authenticate")
        user = maas_factory.make_User()
        mock_authenticate.return_value = defer.succeed(user)
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        self.assertEqual([protocol], factory.clients)

    def test_connectionMade_doesnt_add_self_to_factory_if_auth_fails(self):
        protocol, factory = self.make_protocol()
        mock_authenticate = self.patch(protocol, "authenticate")
        fake_error = maas_factory.make_name()
        mock_authenticate.return_value = defer.fail(Exception(fake_error))
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        self.assertNotIn(protocol, factory.clients)

    def test_connectionMade_extracts_sessionid_and_csrftoken(self):
        protocol, _ = self.make_protocol(patch_authenticate=False)
        sessionid = maas_factory.make_name("sessionid")
        csrftoken = maas_factory.make_name("csrftoken")
        cookies = {
            maas_factory.make_name("key"): maas_factory.make_name("value")
            for _ in range(3)
        }
        cookies["sessionid"] = sessionid
        cookies["csrftoken"] = csrftoken
        protocol.transport.cookies = "; ".join(
            f"{key}={value}" for key, value in cookies.items()
        ).encode("ascii")
        mock_authenticate = self.patch(protocol, "authenticate")
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        mock_authenticate.assert_called_once_with(sessionid, csrftoken)

    def test_connectionLost_removes_self_from_factory(self):
        protocol, factory = self.make_protocol()
        mock_authenticate = self.patch(protocol, "authenticate")
        mock_authenticate.return_value = defer.succeed(None)
        protocol.connectionMade()
        protocol.connectionLost("")
        self.assertEqual([], factory.clients)

    def test_connectionLost_succeeds_if_client_hasnt_been_recorded(self):
        protocol, factory = self.make_protocol()
        self.assertIsNone(protocol.connectionLost(""))
        self.assertEqual([], factory.clients)

    def test_loseConnection_writes_to_log(self):
        protocol, _ = self.make_protocol()
        status = random.randint(1000, 1010)
        reason = maas_factory.make_name("reason")
        with TwistedLoggerFixture() as logger:
            protocol.loseConnection(status, reason)
        self.assertEqual(
            logger.messages, [f"Closing connection: {status!r} ({reason!r})"]
        )

    def test_loseConnection_calls_loseConnection_with_status_and_reason(self):
        protocol, _ = self.make_protocol()
        status = random.randint(1000, 1010)
        reason = maas_factory.make_name("reason")
        protocol.loseConnection(status, reason)
        protocol.transport.loseConnection.assert_called_once_with(
            status, reason.encode("utf-8")
        )

    def test_getMessageField_returns_value_in_message(self):
        protocol, _ = self.make_protocol()
        key = maas_factory.make_name("key")
        value = maas_factory.make_name("value")
        message = {key: value}
        self.assertEqual(value, protocol.getMessageField(message, key))

    def test_getMessageField_calls_loseConnection_if_key_missing(self):
        protocol, _ = self.make_protocol()
        key = maas_factory.make_name("key")
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.assertIsNone(protocol.getMessageField({}, key))
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR,
            f"Missing {key} field in the received message.",
        )

    @synchronous
    @transactional
    def get_user_and_session_id(self):
        user = maas_factory.make_User()
        self.client.login(user=user)
        session_id = self.client.session._session_key
        return user, session_id

    @wait_for_reactor
    @inlineCallbacks
    def test_get_user_and_session_returns_user_and_session(self):
        user, session_id = yield deferToDatabase(self.get_user_and_session_id)
        protocol, _ = self.make_protocol()
        protocol_user, session = yield deferToDatabase(
            lambda: protocol.get_user_and_session(session_id)
        )
        self.assertEqual(user, protocol_user)
        self.assertEqual(session.session_key, session_id)

    def test_get_user_and_session_returns_None_for_invalid_key(self):
        self.client.login(user=maas_factory.make_User())
        session_id = maas_factory.make_name("sessionid")
        protocol, _ = self.make_protocol()
        self.assertIsNone(protocol.get_user_and_session(session_id))

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_user_is_None(self):
        csrftoken = maas_factory.make_name("csrftoken")
        uri = self.make_ws_uri(csrftoken)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        mock_get_user_and_session = self.patch_autospec(
            protocol, "get_user_and_session"
        )
        mock_get_user_and_session.return_value = None

        yield protocol.authenticate(
            maas_factory.make_name("sessionid"), csrftoken
        )
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Failed to authenticate user."
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_error_getting_user(self):
        csrftoken = maas_factory.make_name("csrftoken")
        uri = self.make_ws_uri(csrftoken)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        mock_get_user_and_session = self.patch_autospec(
            protocol, "get_user_and_session"
        )
        mock_get_user_and_session.side_effect = maas_factory.make_exception(
            "unknown reason"
        )

        yield protocol.authenticate(
            maas_factory.make_name("sessionid"), csrftoken
        )
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR,
            "Error authenticating user: unknown reason",
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_invalid_csrftoken(self):
        _, session_id = yield deferToDatabase(self.get_user_and_session_id)
        csrftoken = maas_factory.make_name("csrftoken")
        uri = self.make_ws_uri(csrftoken)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")

        other_csrftoken = maas_factory.make_name("csrftoken")
        yield protocol.authenticate(session_id, other_csrftoken)
        self.assertIsNone(protocol.user)
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Invalid CSRF token."
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_csrftoken_is_missing(self):
        _, session_id = yield deferToDatabase(self.get_user_and_session_id)
        uri = self.make_ws_uri(csrftoken=None)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")

        other_csrftoken = maas_factory.make_name("csrftoken")
        yield protocol.authenticate(session_id, other_csrftoken)
        self.assertIsNone(protocol.user)
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Invalid CSRF token."
        )

    def test_dataReceived_calls_loseConnection_if_json_error(self):
        protocol, _ = self.make_protocol()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.assertEqual(protocol.dataReceived(b"{{{{"), "")
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Invalid data expecting JSON object."
        )

    def test_dataReceived_adds_message_to_queue(self):
        protocol, _ = self.make_protocol()
        self.patch_autospec(protocol, "processMessages")
        message = {"type": MSG_TYPE.REQUEST}
        self.assertEqual(
            protocol.dataReceived(json.dumps(message).encode("ascii")),
            NOT_DONE_YET,
        )
        self.assertEqual(protocol.messages, deque([message]))

    def test_dataReceived_calls_processMessages(self):
        protocol, _ = self.make_protocol()
        mock_processMessages = self.patch_autospec(protocol, "processMessages")
        message = {"type": MSG_TYPE.REQUEST}
        self.assertEqual(
            protocol.dataReceived(json.dumps(message).encode("ascii")),
            NOT_DONE_YET,
        )
        mock_processMessages.assert_called_once_with()

    def test_processMessages_does_nothing_if_no_user(self):
        protocol = WebSocketProtocol()
        protocol.messages = deque(
            [
                {"type": MSG_TYPE.REQUEST, "request_id": 1},
                {"type": MSG_TYPE.REQUEST, "request_id": 2},
            ]
        )
        self.assertEqual([], protocol.processMessages())

    def test_processMessages_process_all_messages_in_the_queue(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        self.patch_autospec(protocol, "handleRequest").return_value = (
            NOT_DONE_YET
        )
        messages = [
            {"type": MSG_TYPE.REQUEST, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
        ]
        protocol.messages = deque(messages)
        self.assertEqual(messages, protocol.processMessages())

    def test_processMessages_calls_loseConnection_if_missing_type_field(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.patch_autospec(protocol, "handleRequest").return_value = (
            NOT_DONE_YET
        )
        messages = [
            {"request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
        ]
        protocol.messages = deque(messages)
        self.assertEqual([messages[0]], protocol.processMessages())
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR,
            "Missing type field in the received message.",
        )

    def test_processMessages_calls_loseConnection_if_type_not_request(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.patch_autospec(protocol, "handleRequest").return_value = (
            NOT_DONE_YET
        )
        messages = [
            {"type": MSG_TYPE.RESPONSE, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
        ]
        protocol.messages = deque(messages)
        self.assertEqual([messages[0]], protocol.processMessages())
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Invalid message type."
        )

    def test_processMessages_stops_processing_msgs_handleRequest_fails(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        self.patch_autospec(protocol, "handleRequest").return_value = None
        messages = [
            {"type": MSG_TYPE.REQUEST, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
        ]
        protocol.messages = deque(messages)
        self.assertEqual([messages[0]], protocol.processMessages())

    def test_processMessages_calls_handleRequest_with_message(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_handleRequest = self.patch_autospec(protocol, "handleRequest")
        mock_handleRequest.return_value = NOT_DONE_YET
        message = {"type": MSG_TYPE.REQUEST, "request_id": 1}
        protocol.messages = deque([message])
        self.assertEqual([message], protocol.processMessages())
        mock_handleRequest.assert_called_once_with(message, MSG_TYPE.REQUEST)

    def test_handleRequest_calls_loseConnection_if_missing_request_id(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {"type": MSG_TYPE.REQUEST}
        self.assertIsNone(protocol.handleRequest(message))
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR,
            "Missing request_id field in the received message.",
        )

    def test_handleRequest_calls_loseConnection_if_missing_method(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {"type": MSG_TYPE.REQUEST, "request_id": 1}
        self.assertIsNone(protocol.handleRequest(message))
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR,
            "Missing method field in the received message.",
        )

    def test_handleRequest_calls_loseConnection_if_bad_method(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "nodes",
        }
        self.assertIsNone(protocol.handleRequest(message))
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Invalid method formatting."
        )

    def test_handleRequest_calls_loseConnection_if_unknown_handler(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "unknown.list",
        }
        self.assertIsNone(protocol.handleRequest(message))
        mock_loseConnection.assert_called_once_with(
            STATUSES.PROTOCOL_ERROR, "Handler unknown does not exist."
        )

    @synchronous
    @transactional
    def make_node(self):
        node = maas_factory.make_Node(with_empty_script_sets=True)
        # Need to ensure a byte string is included in order to fully exercise
        # the JSON encoder.
        fake_lshw = b"""<?xml version="1.0" standalone="yes" ?>
            <!-- generated by lshw-B.02.16 -->
            <!-- GCC 4.8.4 -->
            <!-- Linux 3.13.0-71-generic #114-Ubuntu SMP -->
            <!-- GNU libc 2 (glibc 2.19) -->
            <list>
            <node id="test" claimed="true" class="system" handle="DMI:0100">
            <description>Computer</description>\
            </node>
            </list>"""
        script_set = node.current_commissioning_script_set
        script_result = script_set.find_script_result(
            script_name=LSHW_OUTPUT_NAME
        )
        script_result.store_result(exit_status=0, output=fake_lshw)
        return node

    @wait_for_reactor
    def clean_node(self, node):
        @synchronous
        @transactional
        def delete_node():
            node.delete()

        return deferToDatabase(delete_node)

    def test_handleRequest_builds_handler(self):
        protocol, factory = self.make_protocol()
        protocol.user = sentinel.user

        handler_class = MagicMock()
        handler_name = maas_factory.make_name("handler")
        handler_class._meta.handler_name = handler_name
        handler = handler_class.return_value
        handler.execute.return_value = succeed(None)

        # Inject mock handler into the factory.
        factory.handlers[handler_name] = handler_class

        d = protocol.handleRequest(
            {
                "type": MSG_TYPE.REQUEST,
                "request_id": random.randint(1, 999999),
                "method": "%s.get" % handler_name,
            }
        )

        self.assertTrue(d.called)
        handler_class.assert_called_once_with(
            protocol.user,
            protocol.cache[handler_name],
            protocol.request,
            protocol.session.session_key,
        )
        # The cache passed into the handler constructor *is* the one found in
        # the protocol's cache; they're not merely equal.
        self.assertIs(
            protocol.cache[handler_name], handler_class.call_args[0][1]
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_response(self):
        node = yield deferToDatabase(self.make_node)
        # Need to delete the node as the transaction is committed
        self.addCleanup(self.clean_node, node)

        protocol, _ = self.make_protocol()
        protocol.user = MagicMock()
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "machine.get",
            "params": {"system_id": node.system_id},
        }

        yield protocol.handleRequest(message)
        sent_obj = self.get_written_transport_message(protocol)
        self.assertEqual(sent_obj["type"], MSG_TYPE.RESPONSE)
        self.assertEqual(sent_obj["request_id"], 1)
        self.assertEqual(sent_obj["rtype"], RESPONSE_TYPE.SUCCESS)
        self.assertEqual(sent_obj["result"]["hostname"], node.hostname)

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_validation_error(self):
        node = yield deferToDatabase(self.make_node)
        # Need to delete the node as the transaction is committed
        self.addCleanup(self.clean_node, node)
        protocol, _ = self.make_protocol()
        protocol.user = MagicMock()

        error_dict = {"error": ["bad"]}
        self.patch(Handler, "execute").return_value = fail(
            ValidationError(error_dict)
        )

        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "machine.get",
            "params": {"system_id": node.system_id},
        }

        yield protocol.handleRequest(message)
        sent_obj = self.get_written_transport_message(protocol)
        self.assertEqual(sent_obj["type"], MSG_TYPE.RESPONSE)
        self.assertEqual(sent_obj["request_id"], 1)
        self.assertEqual(sent_obj["rtype"], RESPONSE_TYPE.ERROR)
        self.assertEqual(sent_obj["error"], json.dumps(error_dict))

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_validation_error_without_error_dict(self):
        node = yield deferToDatabase(self.make_node)
        # Need to delete the node as the transaction is committed
        self.addCleanup(self.clean_node, node)
        protocol, _ = self.make_protocol()
        protocol.user = MagicMock()

        self.patch(Handler, "execute").return_value = fail(
            ValidationError("bad")
        )

        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "machine.get",
            "params": {"system_id": node.system_id},
        }

        yield protocol.handleRequest(message)
        sent_obj = self.get_written_transport_message(protocol)
        self.assertEqual(sent_obj["type"], MSG_TYPE.RESPONSE)
        self.assertEqual(sent_obj["request_id"], 1)
        self.assertEqual(sent_obj["rtype"], RESPONSE_TYPE.ERROR)
        self.assertEqual(sent_obj["error"], "bad")

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_error(self):
        node = yield deferToDatabase(self.make_node)
        # Need to delete the node as the transaction is committed
        self.addCleanup(self.clean_node, node)
        protocol, _ = self.make_protocol()
        protocol.user = MagicMock()

        self.patch(Handler, "execute").return_value = fail(
            maas_factory.make_exception("error")
        )

        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "machine.get",
            "params": {"system_id": node.system_id},
        }

        yield protocol.handleRequest(message)
        sent_obj = self.get_written_transport_message(protocol)
        self.assertEqual(sent_obj["type"], MSG_TYPE.RESPONSE)
        self.assertEqual(sent_obj["request_id"], 1)
        self.assertEqual(sent_obj["rtype"], RESPONSE_TYPE.ERROR)
        self.assertEqual(sent_obj["error"], "error")

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_ping_reply_on_ping(self):
        protocol, _ = self.make_protocol()
        protocol.user = MagicMock()

        request_id = random.choice([1, 3, 5, 7, 9])
        seq = random.choice([0, 2, 4, 6, 8])
        protocol.sequence_number = seq

        message = {"type": MSG_TYPE.PING, "request_id": request_id}

        yield protocol.handleRequest(message, msg_type=MSG_TYPE.PING)
        sent_obj = self.get_written_transport_message(protocol)
        self.assertEqual(sent_obj["type"], MSG_TYPE.PING_REPLY)
        self.assertEqual(sent_obj["request_id"], request_id)
        self.assertEqual(sent_obj["result"], seq + 1)

    def test_sendNotify_sends_correct_json(self):
        protocol, _ = self.make_protocol()
        name = maas_factory.make_name("name")
        action = maas_factory.make_name("action")
        data = maas_factory.make_name("data")
        message = {
            "type": MSG_TYPE.NOTIFY,
            "name": name,
            "action": action,
            "data": data,
        }
        protocol.sendNotify(name, action, data)
        self.assertEqual(message, self.get_written_transport_message(protocol))


class MakeProtocolFactoryMixin:
    def make_factory(self, rpc_service=None):
        listener = FakePostgresListenerService()
        factory = WebSocketFactory(listener)
        if rpc_service is None:
            rpc_service = MagicMock()
        self.patch(services, "getServiceNamed").return_value = rpc_service
        return factory

    def make_protocol_with_factory(self, user=None, rpc_service=None):
        factory = self.make_factory(rpc_service=rpc_service)
        factory.startFactory()
        self.addCleanup(factory.stopFactory)
        protocol = factory.buildProtocol(None)
        protocol.transport = MagicMock()
        protocol.transport.cookies = b""
        protocol.session = MagicMock()
        protocol.session.session_key = ""
        if user is None:
            user = maas_factory.make_User()

        def authenticate(*args):
            protocol.user = user
            return defer.succeed(True)

        self.patch(protocol, "authenticate", authenticate)
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        return protocol, factory


ALL_NOTIFIERS = {
    "config",
    "controller",
    "device",
    "dhcpsnippet",
    "domain",
    "event",
    "fabric",
    "iprange",
    "machine",
    "nodedevice",
    "notification",
    "notificationdismissal",
    "packagerepository",
    "pod",
    "resourcepool",
    "script",
    "scriptresult",
    "service",
    "space",
    "sshkey",
    "sslkey",
    "staticroute",
    "subnet",
    "tag",
    "token",
    "user",
    "vlan",
    "vmcluster",
    "zone",
}

ALL_HANDLERS = {
    "bootresource",
    "config",
    "controller",
    "device",
    "dhcpsnippet",
    "discovery",
    "domain",
    "event",
    "fabric",
    "general",
    "iprange",
    "machine",
    "msm",
    "nodedevice",
    "noderesult",
    "notification",
    "packagerepository",
    "pod",
    "resourcepool",
    "script",
    "service",
    "space",
    "sshkey",
    "sslkey",
    "staticroute",
    "subnet",
    "tag",
    "token",
    "user",
    "vlan",
    "vmcluster",
    "zone",
}


class TestWebSocketFactory(MAASTestCase, MakeProtocolFactoryMixin):
    def test_loads_all_handlers(self):
        factory = self.make_factory()
        self.assertEqual(ALL_HANDLERS, factory.handlers.keys())

    def test_get_SessionEngine_calls_import_module_with_SESSION_ENGINE(self):
        getModule = self.patch_autospec(protocol_module, "getModule")
        factory = self.make_factory()
        factory.getSessionEngine()
        # A reference to the module was obtained via getModule.
        getModule.assert_called_once_with(
            protocol_module.settings.SESSION_ENGINE
        )
        # It was then loaded via that reference.
        getModule.return_value.load.assert_called_once_with()

    def test_getHandler_returns_None_on_missing_handler(self):
        factory = self.make_factory()
        self.assertIsNone(factory.getHandler("unknown"))

    def test_getHandler_returns_MachineHandler(self):
        factory = self.make_factory()
        self.assertIs(MachineHandler, factory.getHandler("machine"))

    def test_getHandler_returns_DeviceHandler(self):
        factory = self.make_factory()
        self.assertIs(DeviceHandler, factory.getHandler("device"))

    def test_buildProtocol_returns_WebSocketProtocol(self):
        factory = self.make_factory()
        self.assertIsInstance(
            factory.buildProtocol(sentinel.addr), WebSocketProtocol
        )

    def test_startFactory_registers_rpc_handlers(self):
        rpc_service = MagicMock()
        factory = self.make_factory(rpc_service)
        factory.startFactory()
        try:
            rpc_service.events.connected.registerHandler.assert_called_once_with(
                factory.updateRackController
            )
            rpc_service.events.disconnected.registerHandler.assert_called_once_with(
                factory.updateRackController
            )
        finally:
            factory.stopFactory()

    def test_stopFactory_unregisters_rpc_handlers(self):
        rpc_service = MagicMock()
        factory = self.make_factory(rpc_service)
        factory.startFactory()
        factory.stopFactory()
        rpc_service.events.connected.unregisterHandler.assert_called_once_with(
            factory.updateRackController
        )
        rpc_service.events.disconnected.unregisterHandler.assert_called_once_with(
            factory.updateRackController
        )

    def test_registerNotifiers_registers_all_notifiers(self):
        factory = self.make_factory()
        self.assertEqual(ALL_NOTIFIERS, factory.listener.listeners.keys())


class TestWebSocketFactoryTransactional(
    MAASTransactionServerTestCase, MakeProtocolFactoryMixin
):
    @transactional
    def make_user(self):
        return maas_factory.make_User()

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_creates_handler_class_with_protocol_user(self):
        user = yield deferToDatabase(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = None
        yield factory.onNotify(
            mock_class, sentinel.channel, sentinel.action, sentinel.obj_id
        )
        self.assertIs(protocol.user, mock_class.call_args[0][0])

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_creates_handler_class_with_protocol_cache(self):
        user = yield deferToDatabase(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        handler_class = MagicMock()
        handler_class.return_value.on_listen.return_value = None
        handler_class._meta.handler_name = maas_factory.make_name("handler")
        yield factory.onNotify(
            handler_class, sentinel.channel, sentinel.action, sentinel.obj_id
        )
        handler_class.assert_called_once_with(
            user,
            protocol.cache[handler_class._meta.handler_name],
            protocol.request,
            protocol.session.session_key,
        )
        # The cache passed into the handler constructor *is* the one found in
        # the protocol's cache; they're not merely equal.
        self.assertIs(
            protocol.cache[handler_class._meta.handler_name],
            handler_class.call_args[0][1],
            handler_class.call_args[0][2],
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_calls_handler_class_on_listen(self):
        user = yield deferToDatabase(self.make_user)
        _, factory = self.make_protocol_with_factory(user=user)
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = None
        yield factory.onNotify(
            mock_class, sentinel.channel, sentinel.action, sentinel.obj_id
        )
        mock_class.return_value.on_listen.assert_called_with(
            sentinel.channel, sentinel.action, sentinel.obj_id
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_calls_sendNotify_on_protocol(self):
        user = yield deferToDatabase(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        name = maas_factory.make_name("name")
        action = maas_factory.make_name("action")
        data = maas_factory.make_name("data")
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = (name, action, data)
        mock_sendNotify = self.patch(protocol, "sendNotify")
        yield factory.onNotify(
            mock_class, sentinel.channel, action, sentinel.obj_id
        )
        mock_sendNotify.assert_called_with(name, action, data)

    @wait_for_reactor
    @inlineCallbacks
    def test_updateRackController_calls_onNotify_for_controller_update(self):
        user = yield deferToDatabase(transactional(maas_factory.make_User))
        controller = yield deferToDatabase(
            transactional(maas_factory.make_RackController)
        )
        _, factory = self.make_protocol_with_factory(user=user)
        mock_onNotify = self.patch(factory, "onNotify")
        controller_handler = MagicMock()
        factory.handlers["controller"] = controller_handler
        yield factory.updateRackController(controller.system_id)
        mock_onNotify.assert_called_once_with(
            controller_handler,
            "controller",
            "update",
            controller.system_id,
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_check_sessions(self):
        factory = self.make_factory()

        session_engine = factory.getSessionEngine()
        Session = session_engine.SessionStore.get_model_class()
        key1 = maas_factory.make_string()
        key2 = maas_factory.make_string()

        def make_sessions():
            now = datetime.utcnow()
            delta = timedelta(hours=1)
            # first session is expired, second one is valid
            return (
                Session.objects.create(
                    session_key=key1, expire_date=now - delta
                ),
                Session.objects.create(
                    session_key=key2, expire_date=now + delta
                ),
            )

        expired_session, active_session = yield deferToDatabase(make_sessions)

        def make_protocol_with_session(session):
            protocol = factory.buildProtocol(None)
            protocol.transport = MagicMock()
            protocol.transport.cookies = b""

            def authenticate(*args):
                protocol.session = session
                return defer.succeed(True)

            self.patch(protocol, "authenticate", authenticate)
            self.patch(protocol, "loseConnection")
            return protocol

        expired_proto = make_protocol_with_session(expired_session)
        active_proto = make_protocol_with_session(active_session)

        yield expired_proto.connectionMade()
        self.addCleanup(expired_proto.connectionLost, "")
        yield active_proto.connectionMade()
        self.addCleanup(active_proto.connectionLost, "")

        yield factory.startFactory()
        factory.stopFactory()
        # wait until it's stopped, sessions are checked
        yield factory.session_checker_done
        # the first client gets disconnected
        expired_proto.loseConnection.assert_called_once_with(
            STATUSES.NORMAL, "Session expired"
        )
        active_proto.loseConnection.assert_not_called()

    @wait_for_reactor
    @inlineCallbacks
    def test_session_checker_stopped_with_previous_failure(self):
        factory = self.make_factory()
        mock_session_checker = self.patch(factory, "session_checker")
        self.patch(factory, "unregisterRPCEvents").side_effect = Exception(
            "err"
        )
        yield factory.startFactory()
        err = self.assertRaises(Exception, factory.stopFactory)
        self.assertEqual(str(err), "err")
        mock_session_checker.stop.assert_called_once()
