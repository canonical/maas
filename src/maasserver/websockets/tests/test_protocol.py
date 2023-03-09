# Copyright 2015-2023 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from collections import deque
import json
import random
from unittest.mock import MagicMock, sentinel

from django.core.exceptions import ValidationError
from django.http import HttpRequest
from testtools.matchers import Equals, Is
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
from maastesting.matchers import (
    IsFiredDeferred,
    MockCalledOnceWith,
    MockCalledWith,
)
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
        protocol, factory = self.make_protocol(patch_authenticate=False)
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
        protocol, factory = self.make_protocol(patch_authenticate=False)
        self.patch_autospec(protocol, "authenticate")
        self.patch_autospec(protocol, "processMessages")
        mock_splithost = self.patch_autospec(protocol_module, "splithost")
        mock_splithost.return_value = (None, None)
        protocol.authenticate.return_value = defer.succeed(sentinel.user)
        protocol.connectionMade()
        self.addCleanup(protocol.connectionLost, "")
        self.assertEqual(protocol.request.META["SERVER_NAME"], "localhost")
        self.assertEqual(protocol.request.META["SERVER_PORT"], 5248)

    def test_connectionMade_sets_user_and_processes_messages(self):
        protocol, factory = self.make_protocol(patch_authenticate=False)
        self.patch_autospec(protocol, "authenticate")
        self.patch_autospec(protocol, "processMessages")
        protocol.authenticate.return_value = defer.succeed(sentinel.user)
        protocol.connectionMade()
        self.addCleanup(protocol.connectionLost, "")
        self.assertIs(protocol.user, sentinel.user)
        self.assertThat(protocol.processMessages, MockCalledOnceWith())

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
        protocol, factory = self.make_protocol(patch_authenticate=False)
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
        self.assertThat(
            mock_authenticate, MockCalledOnceWith(sessionid, csrftoken)
        )

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
        protocol, factory = self.make_protocol()
        status = random.randint(1000, 1010)
        reason = maas_factory.make_name("reason")
        with TwistedLoggerFixture() as logger:
            protocol.loseConnection(status, reason)
        self.assertThat(
            logger.messages,
            Equals(
                [
                    "Closing connection: %(status)r (%(reason)r)"
                    % dict(status=status, reason=reason)
                ]
            ),
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
        self.expectThat(protocol.getMessageField({}, key), Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing %s field in the received message." % key,
            ),
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
    def test_getUserFromSessionId_returns_User(self):
        user, session_id = yield deferToDatabase(self.get_user_and_session_id)
        protocol, _ = self.make_protocol()
        protocol_user = yield deferToDatabase(
            lambda: protocol.getUserFromSessionId(session_id)
        )
        self.assertEqual(user, protocol_user)

    def test_getUserFromSessionId_returns_None_for_invalid_key(self):
        self.client.login(user=maas_factory.make_User())
        session_id = maas_factory.make_name("sessionid")
        protocol, _ = self.make_protocol()
        self.assertIsNone(protocol.getUserFromSessionId(session_id))

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_user_is_None(self):
        csrftoken = maas_factory.make_name("csrftoken")
        uri = self.make_ws_uri(csrftoken)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        mock_getUserFromSessionId = self.patch_autospec(
            protocol, "getUserFromSessionId"
        )
        mock_getUserFromSessionId.return_value = None

        yield protocol.authenticate(
            maas_factory.make_name("sessionid"), csrftoken
        )
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR, "Failed to authenticate user."
            ),
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
        mock_getUserFromSessionId = self.patch_autospec(
            protocol, "getUserFromSessionId"
        )
        mock_getUserFromSessionId.side_effect = maas_factory.make_exception(
            "unknown reason"
        )

        yield protocol.authenticate(
            maas_factory.make_name("sessionid"), csrftoken
        )
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Error authenticating user: unknown reason",
            ),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_invalid_csrftoken(self):
        user, session_id = yield deferToDatabase(self.get_user_and_session_id)
        csrftoken = maas_factory.make_name("csrftoken")
        uri = self.make_ws_uri(csrftoken)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")

        other_csrftoken = maas_factory.make_name("csrftoken")
        yield protocol.authenticate(session_id, other_csrftoken)
        self.expectThat(protocol.user, Equals(None))

        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(STATUSES.PROTOCOL_ERROR, "Invalid CSRF token."),
        )

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_csrftoken_is_missing(self):
        user, session_id = yield deferToDatabase(self.get_user_and_session_id)
        uri = self.make_ws_uri(csrftoken=None)
        protocol, _ = self.make_protocol(
            patch_authenticate=False, transport_uri=uri
        )
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")

        other_csrftoken = maas_factory.make_name("csrftoken")
        yield protocol.authenticate(session_id, other_csrftoken)
        self.expectThat(protocol.user, Equals(None))

        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(STATUSES.PROTOCOL_ERROR, "Invalid CSRF token."),
        )

    def test_dataReceived_calls_loseConnection_if_json_error(self):
        protocol, _ = self.make_protocol()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.expectThat(protocol.dataReceived(b"{{{{"), Is(""))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR, "Invalid data expecting JSON object."
            ),
        )

    def test_dataReceived_adds_message_to_queue(self):
        protocol, _ = self.make_protocol()
        self.patch_autospec(protocol, "processMessages")
        message = {"type": MSG_TYPE.REQUEST}
        self.expectThat(
            protocol.dataReceived(json.dumps(message).encode("ascii")),
            Is(NOT_DONE_YET),
        )
        self.expectThat(protocol.messages, Equals(deque([message])))

    def test_dataReceived_calls_processMessages(self):
        protocol, _ = self.make_protocol()
        mock_processMessages = self.patch_autospec(protocol, "processMessages")
        message = {"type": MSG_TYPE.REQUEST}
        self.expectThat(
            protocol.dataReceived(json.dumps(message).encode("ascii")),
            Is(NOT_DONE_YET),
        )
        self.expectThat(mock_processMessages, MockCalledOnceWith())

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
        self.patch_autospec(
            protocol, "handleRequest"
        ).return_value = NOT_DONE_YET
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
        self.patch_autospec(
            protocol, "handleRequest"
        ).return_value = NOT_DONE_YET
        messages = [
            {"request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
        ]
        protocol.messages = deque(messages)
        self.expectThat([messages[0]], Equals(protocol.processMessages()))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing type field in the received message.",
            ),
        )

    def test_processMessages_calls_loseConnection_if_type_not_request(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.patch_autospec(
            protocol, "handleRequest"
        ).return_value = NOT_DONE_YET
        messages = [
            {"type": MSG_TYPE.RESPONSE, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
        ]
        protocol.messages = deque(messages)
        self.expectThat([messages[0]], Equals(protocol.processMessages()))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR, "Invalid message type."
            ),
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
        self.expectThat([messages[0]], Equals(protocol.processMessages()))

    def test_processMessages_calls_handleRequest_with_message(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_handleRequest = self.patch_autospec(protocol, "handleRequest")
        mock_handleRequest.return_value = NOT_DONE_YET
        message = {"type": MSG_TYPE.REQUEST, "request_id": 1}
        protocol.messages = deque([message])
        self.expectThat([message], Equals(protocol.processMessages()))
        self.expectThat(
            mock_handleRequest, MockCalledOnceWith(message, MSG_TYPE.REQUEST)
        )

    def test_handleRequest_calls_loseConnection_if_missing_request_id(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {"type": MSG_TYPE.REQUEST}
        self.expectThat(protocol.handleRequest(message), Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing request_id field in the received message.",
            ),
        )

    def test_handleRequest_calls_loseConnection_if_missing_method(self):
        protocol, _ = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {"type": MSG_TYPE.REQUEST, "request_id": 1}
        self.expectThat(protocol.handleRequest(message), Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing method field in the received message.",
            ),
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
        self.expectThat(protocol.handleRequest(message), Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR, "Invalid method formatting."
            ),
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
        self.expectThat(protocol.handleRequest(message), Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR, "Handler unknown does not exist."
            ),
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

        self.assertThat(d, IsFiredDeferred())
        self.assertThat(
            handler_class,
            MockCalledOnceWith(
                protocol.user, protocol.cache[handler_name], protocol.request
            ),
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
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.RESPONSE))
        self.expectThat(sent_obj["request_id"], Equals(1))
        self.expectThat(sent_obj["rtype"], Equals(RESPONSE_TYPE.SUCCESS))
        self.expectThat(sent_obj["result"]["hostname"], Equals(node.hostname))

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
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.RESPONSE))
        self.expectThat(sent_obj["request_id"], Equals(1))
        self.expectThat(sent_obj["rtype"], Equals(RESPONSE_TYPE.ERROR))
        self.expectThat(sent_obj["error"], Equals(json.dumps(error_dict)))

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
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.RESPONSE))
        self.expectThat(sent_obj["request_id"], Equals(1))
        self.expectThat(sent_obj["rtype"], Equals(RESPONSE_TYPE.ERROR))
        self.expectThat(sent_obj["error"], Equals("bad"))

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
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.RESPONSE))
        self.expectThat(sent_obj["request_id"], Equals(1))
        self.expectThat(sent_obj["rtype"], Equals(RESPONSE_TYPE.ERROR))
        self.expectThat(sent_obj["error"], Equals("error"))

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
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.PING_REPLY))
        self.expectThat(sent_obj["request_id"], Equals(request_id))
        self.expectThat(sent_obj["result"], Equals(seq + 1))

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
        if user is None:
            user = maas_factory.make_User()
        mock_authenticate = self.patch(protocol, "authenticate")
        mock_authenticate.return_value = defer.succeed(user)
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
        self.assertThat(
            getModule,
            MockCalledOnceWith(protocol_module.settings.SESSION_ENGINE),
        )
        # It was then loaded via that reference.
        self.assertThat(getModule.return_value.load, MockCalledOnceWith())

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
            self.expectThat(
                rpc_service.events.connected.registerHandler,
                MockCalledOnceWith(factory.updateRackController),
            )
            self.expectThat(
                rpc_service.events.disconnected.registerHandler,
                MockCalledOnceWith(factory.updateRackController),
            )
        finally:
            factory.stopFactory()

    def test_stopFactory_unregisters_rpc_handlers(self):
        rpc_service = MagicMock()
        factory = self.make_factory(rpc_service)
        factory.startFactory()
        factory.stopFactory()
        self.expectThat(
            rpc_service.events.connected.unregisterHandler,
            MockCalledOnceWith(factory.updateRackController),
        )
        self.expectThat(
            rpc_service.events.disconnected.unregisterHandler,
            MockCalledOnceWith(factory.updateRackController),
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
        self.assertThat(
            handler_class,
            MockCalledOnceWith(
                user,
                protocol.cache[handler_class._meta.handler_name],
                protocol.request,
            ),
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
        protocol, factory = self.make_protocol_with_factory(user=user)
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = None
        yield factory.onNotify(
            mock_class, sentinel.channel, sentinel.action, sentinel.obj_id
        )
        self.assertThat(
            mock_class.return_value.on_listen,
            MockCalledWith(sentinel.channel, sentinel.action, sentinel.obj_id),
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
        self.assertThat(mock_sendNotify, MockCalledWith(name, action, data))

    @wait_for_reactor
    @inlineCallbacks
    def test_updateRackController_calls_onNotify_for_controller_update(self):
        user = yield deferToDatabase(transactional(maas_factory.make_User))
        controller = yield deferToDatabase(
            transactional(maas_factory.make_RackController)
        )
        protocol, factory = self.make_protocol_with_factory(user=user)
        mock_onNotify = self.patch(factory, "onNotify")
        controller_handler = MagicMock()
        factory.handlers["controller"] = controller_handler
        yield factory.updateRackController(controller.system_id)
        self.assertThat(
            mock_onNotify,
            MockCalledOnceWith(
                controller_handler,
                "controller",
                "update",
                controller.system_id,
            ),
        )
