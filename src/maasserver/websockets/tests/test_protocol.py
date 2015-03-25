# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.websockets.protocol`"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from collections import deque
import json
import random

from crochet import wait_for_reactor
from maasserver.testing.factory import factory as maas_factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils.orm import transactional
from maasserver.websockets import protocol as protocol_module
from maasserver.websockets.handlers import (
    DeviceHandler,
    NodeHandler,
    )
from maasserver.websockets.protocol import (
    MSG_TYPE,
    RESPONSE_TYPE,
    WebSocketFactory,
    WebSocketProtocol,
    )
from maasserver.websockets.websockets import STATUSES
from maastesting.matchers import (
    MockCalledOnceWith,
    MockCalledWith,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    MagicMock,
    sentinel,
    )
from provisioningserver.utils.twisted import synchronous
from testtools.matchers import (
    Equals,
    Is,
    )
from twisted.internet.defer import (
    fail,
    inlineCallbacks,
    )
from twisted.internet.threads import deferToThread
from twisted.web.server import NOT_DONE_YET


class TestWebSocketProtocol(MAASServerTestCase):

    def make_protocol(self, patch_authenticate=True):
        self.patch(protocol_module, "PostgresListener")
        factory = WebSocketFactory()
        protocol = factory.buildProtocol(None)
        protocol.transport = MagicMock()
        if patch_authenticate:
            self.patch(protocol, "authenticate")
        return protocol, factory

    def get_written_transport_message(self, protocol):
        call = protocol.transport.write.call_args_list.pop()
        return json.loads(call[0][0])

    def test_connectionMade_adds_self_to_factory(self):
        protocol, factory = self.make_protocol()
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        self.assertItemsEqual(
            [protocol], factory.clients)

    def test_connectionMade_extracts_sessionid_from_cookies(self):
        protocol, factory = self.make_protocol(patch_authenticate=False)
        sessionid = maas_factory.make_name("sessionid")
        cookies = {
            maas_factory.make_name("key"): maas_factory.make_name("value")
            for _ in range(3)
            }
        cookies["sessionid"] = sessionid
        protocol.transport.cookies = "; ".join(
            "%s=%s" % (key, value)
            for key, value in cookies.items())
        mock_authenticate = self.patch(protocol, "authenticate")
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        self.assertThat(mock_authenticate, MockCalledOnceWith(sessionid))

    def test_connectionLost_removes_self_from_factory(self):
        protocol, factory = self.make_protocol()
        protocol.connectionMade()
        protocol.connectionLost("")
        self.assertItemsEqual(
            [], factory.clients)

    def test_loseConnection_writes_to_log(self):
        protocol, factory = self.make_protocol()
        mock_log_msg = self.patch_autospec(protocol_module.log, "msg")
        status = random.randint(1000, 1010)
        reason = maas_factory.make_name("reason")
        protocol.loseConnection(status, reason)
        self.assertThat(
            mock_log_msg,
            MockCalledOnceWith(
                format="Closing connection: %(status)r (%(reason)r)",
                status=status, reason=reason))

    def test_loseConnection_calls_loseConnection_with_status_and_reason(self):
        protocol, factory = self.make_protocol()
        status = random.randint(1000, 1010)
        reason = maas_factory.make_name("reason")
        protocol.loseConnection(status, reason)
        self.assertThat(
            protocol.transport._receiver._transport.loseConnection,
            MockCalledOnceWith(status, reason.encode("utf-8")))

    def test_getMessageField_returns_value_in_message(self):
        protocol, factory = self.make_protocol()
        key = maas_factory.make_name("key")
        value = maas_factory.make_name("value")
        message = {key: value}
        self.assertEquals(value, protocol.getMessageField(message, key))

    def test_getMessageField_calls_loseConnection_if_key_missing(self):
        protocol, factory = self.make_protocol()
        key = maas_factory.make_name("key")
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.expectThat(protocol.getMessageField({}, key), Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing %s field in the received message." % key))

    @synchronous
    @transactional
    def get_user_and_session_id(self):
        self.client_log_in()
        user = self.logged_in_user
        session_id = self.client.session._session_key
        return user, session_id

    @wait_for_reactor
    @inlineCallbacks
    def test_getUserFromSessionId_returns_User(self):
        user, session_id = yield deferToThread(self.get_user_and_session_id)
        protocol, factory = self.make_protocol()
        protocol_user = yield deferToThread(
            lambda: protocol.getUserFromSessionId(session_id))
        self.assertEquals(user, protocol_user)

    def test_getUserFromSessionId_returns_None_for_invalid_key(self):
        self.client_log_in()
        session_id = maas_factory.make_name("sessionid")
        protocol, factory = self.make_protocol()
        self.assertIs(
            None,
            protocol.getUserFromSessionId(session_id))

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_sets_users(self):
        user, session_id = yield deferToThread(self.get_user_and_session_id)
        protocol, factory = self.make_protocol(patch_authenticate=False)
        yield protocol.authenticate(session_id)
        self.expectThat(
            user, Equals(protocol.user))

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_user_is_None(self):
        protocol, factory = self.make_protocol(patch_authenticate=False)
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        mock_getUserFromSessionId = self.patch_autospec(
            protocol, "getUserFromSessionId")
        mock_getUserFromSessionId.return_value = None

        yield protocol.authenticate(maas_factory.make_name("sessionid"))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Failed to authenticate user."))

    @wait_for_reactor
    @inlineCallbacks
    def test_authenticate_calls_loseConnection_if_error_getting_user(self):
        protocol, factory = self.make_protocol(patch_authenticate=False)
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        mock_getUserFromSessionId = self.patch_autospec(
            protocol, "getUserFromSessionId")
        mock_getUserFromSessionId.side_effect = maas_factory.make_exception(
            "unknown reason")

        yield protocol.authenticate(maas_factory.make_name("sessionid"))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Error authenticating user: unknown reason"))

    def test_dataReceived_calls_loseConnection_if_json_error(self):
        protocol, factory = self.make_protocol()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.expectThat(protocol.dataReceived("{{{{"), Is(""))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Invalid data expecting JSON object."))

    def test_dataReceived_adds_message_to_queue(self):
        protocol, factory = self.make_protocol()
        self.patch_autospec(protocol, "processMessages")
        message = {"type": MSG_TYPE.REQUEST}
        self.expectThat(
            protocol.dataReceived(json.dumps(message)), Is(NOT_DONE_YET))
        self.expectThat(protocol.messages, Equals(deque([message])))

    def test_dataReceived_calls_processMessages(self):
        protocol, factory = self.make_protocol()
        mock_processMessages = self.patch_autospec(protocol, "processMessages")
        message = {"type": MSG_TYPE.REQUEST}
        self.expectThat(
            protocol.dataReceived(json.dumps(message)), Is(NOT_DONE_YET))
        self.expectThat(mock_processMessages, MockCalledOnceWith())

    def test_processMessages_does_nothing_if_no_user(self):
        protocol = WebSocketProtocol(None)
        protocol.messages = deque([
            {"type": MSG_TYPE.REQUEST, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
            ])
        self.assertEquals([], protocol.processMessages())

    def test_processMessages_process_all_messages_in_the_queue(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        self.patch_autospec(
            protocol, "handleRequest").return_value = NOT_DONE_YET
        messages = [
            {"type": MSG_TYPE.REQUEST, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
            ]
        protocol.messages = deque(messages)
        self.assertEquals(messages, protocol.processMessages())

    def test_processMessages_calls_loseConnection_if_missing_type_field(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.patch_autospec(
            protocol, "handleRequest").return_value = NOT_DONE_YET
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
                "Missing type field in the received message."))

    def test_processMessages_calls_loseConnection_if_type_not_request(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        self.patch_autospec(
            protocol, "handleRequest").return_value = NOT_DONE_YET
        messages = [
            {"type": MSG_TYPE.RESPONSE, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
            ]
        protocol.messages = deque(messages)
        self.expectThat([messages[0]], Equals(protocol.processMessages()))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Invalid message type."))

    def test_processMessages_stops_processing_msgs_handleRequest_fails(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        self.patch_autospec(
            protocol, "handleRequest").return_value = None
        messages = [
            {"type": MSG_TYPE.REQUEST, "request_id": 1},
            {"type": MSG_TYPE.REQUEST, "request_id": 2},
            ]
        protocol.messages = deque(messages)
        self.expectThat([messages[0]], Equals(protocol.processMessages()))

    def test_processMessages_calls_handleRequest_with_message(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_handleRequest = self.patch_autospec(
            protocol, "handleRequest")
        mock_handleRequest.return_value = NOT_DONE_YET
        message = {"type": MSG_TYPE.REQUEST, "request_id": 1}
        protocol.messages = deque([message])
        self.expectThat([message], Equals(protocol.processMessages()))
        self.expectThat(
            mock_handleRequest,
            MockCalledOnceWith(message))

    def test_handleRequest_calls_loseConnection_if_missing_request_id(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {"type": MSG_TYPE.REQUEST}
        self.expectThat(
            protocol.handleRequest(message),
            Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing request_id field in the received message."))

    def test_handleRequest_calls_loseConnection_if_missing_method(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            }
        self.expectThat(
            protocol.handleRequest(message),
            Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Missing method field in the received message."))

    def test_handleRequest_calls_loseConnection_if_bad_method(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "nodes",
            }
        self.expectThat(
            protocol.handleRequest(message),
            Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Invalid method formatting."))

    def test_handleRequest_calls_loseConnection_if_unknown_handler(self):
        protocol, factory = self.make_protocol()
        protocol.user = maas_factory.make_User()
        mock_loseConnection = self.patch_autospec(protocol, "loseConnection")
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "unknown.list",
            }
        self.expectThat(
            protocol.handleRequest(message),
            Is(None))
        self.expectThat(
            mock_loseConnection,
            MockCalledOnceWith(
                STATUSES.PROTOCOL_ERROR,
                "Handler unknown does not exist."))

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_calls_execute_with_transactional_func(self):
        protocol, factory = self.make_protocol()
        protocol.user = MagicMock()
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "node.get",
            "params": {}
            }

        expected_result = maas_factory.make_name("result")

        def fake_wrapper(*args, **kwargs):
            return expected_result

        mock_transactional = self.patch(protocol_module, "transactional")
        mock_transactional.return_value = fake_wrapper
        observed_result = yield protocol.handleRequest(message)
        self.assertEquals(expected_result, observed_result)

    @synchronous
    @transactional
    def make_node(self):
        return maas_factory.make_Node()

    @wait_for_reactor
    def clean_node(self, node):

        @synchronous
        @transactional
        def delete_node():
            node.delete()

        return deferToThread(delete_node)

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_response(self):
        node = yield deferToThread(self.make_node)
        # Need to delete the node as the transaction is committed
        self.addCleanup(self.clean_node, node)

        protocol, factory = self.make_protocol()
        protocol.user = MagicMock()
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "node.get",
            "params": {
                "system_id": node.system_id,
                }
            }

        yield protocol.handleRequest(message)
        sent_obj = self.get_written_transport_message(protocol)
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.RESPONSE))
        self.expectThat(sent_obj["request_id"], Equals(1))
        self.expectThat(sent_obj["rtype"], Equals(RESPONSE_TYPE.SUCCESS))
        self.expectThat(sent_obj["result"]["hostname"], Equals(node.hostname))

    @wait_for_reactor
    @inlineCallbacks
    def test_handleRequest_sends_error(self):
        node = yield deferToThread(self.make_node)
        # Need to delete the node as the transaction is committed
        self.addCleanup(self.clean_node, node)
        protocol, factory = self.make_protocol()
        protocol.user = MagicMock()
        mock_deferToThread = self.patch_autospec(
            protocol_module, "deferToThread")
        mock_deferToThread.return_value = fail(
            maas_factory.make_exception("error"))
        message = {
            "type": MSG_TYPE.REQUEST,
            "request_id": 1,
            "method": "node.get",
            "params": {
                "system_id": node.system_id,
                }
            }

        yield protocol.handleRequest(message)
        sent_obj = self.get_written_transport_message(protocol)
        self.expectThat(sent_obj["type"], Equals(MSG_TYPE.RESPONSE))
        self.expectThat(sent_obj["request_id"], Equals(1))
        self.expectThat(sent_obj["rtype"], Equals(RESPONSE_TYPE.ERROR))
        self.expectThat(sent_obj["error"], Equals("error"))

    def test_sendNotify_sends_correct_json(self):
        protocol, factory = self.make_protocol()
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
        self.assertEquals(
            message, self.get_written_transport_message(protocol))


class TestWebSocketFactory(MAASTestCase):

    def make_protocol_with_factory(self, user=None):
        factory = WebSocketFactory()
        protocol = factory.buildProtocol(None)
        protocol.transport = MagicMock()
        if user is None:
            user = maas_factory.make_User()
        protocol.user = user
        self.patch(protocol, "authenticate")
        protocol.connectionMade()
        self.addCleanup(lambda: protocol.connectionLost(""))
        return protocol, factory

    def test_loads_all_handlers(self):
        factory = WebSocketFactory()
        self.assertItemsEqual(
            ["device", "general", "node", "cluster", "zone"],
            factory.handlers.keys())

    def test_get_SessionEngine_calls_import_module_with_SESSION_ENGINE(self):
        mock_import = self.patch_autospec(protocol_module, "import_module")
        factory = WebSocketFactory()
        factory.getSessionEngine()
        self.assertThat(
            mock_import,
            MockCalledOnceWith(protocol_module.settings.SESSION_ENGINE))

    def test_getHandler_returns_None_on_missing_handler(self):
        factory = WebSocketFactory()
        self.assertIsNone(factory.getHandler("unknown"))

    def test_getHandler_returns_NodeHandler(self):
        factory = WebSocketFactory()
        self.assertIs(
            NodeHandler,
            factory.getHandler("node"))

    def test_getHandler_returns_DeviceHandler(self):
        factory = WebSocketFactory()
        self.assertIs(
            DeviceHandler,
            factory.getHandler("device"))

    def test_buildProtocol_returns_WebSocketProtocol(self):
        factory = WebSocketFactory()
        self.assertIsInstance(
            factory.buildProtocol(sentinel.addr), WebSocketProtocol)

    @wait_for_reactor
    @inlineCallbacks
    def test_startFactory_starts_listener(self):
        factory = WebSocketFactory()
        yield factory.startFactory()
        try:
            self.expectThat(factory.listener.connected(), Equals(True))
        finally:
            yield factory.stopFactory()

    @wait_for_reactor
    @inlineCallbacks
    def test_stopFactory_stops_listener(self):
        factory = WebSocketFactory()
        yield factory.startFactory()
        yield factory.stopFactory()
        self.expectThat(factory.listener.connected(), Equals(False))

    def test_registerNotifiers_registers_all_notifiers(self):
        factory = WebSocketFactory()
        self.assertItemsEqual(
            ["node", "device", "nodegroup", "zone"],
            factory.listener.listeners.keys())

    @transactional
    def make_user(self):
        return maas_factory.make_User()

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_creates_handler_class_with_protocol_user(self):
        user = yield deferToThread(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = None
        yield factory.onNotify(
            mock_class, sentinel.channel, sentinel.action, sentinel.obj_id)
        self.assertIs(
            protocol.user, mock_class.call_args[0][0])

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_creates_handler_class_with_protocol_cache(self):
        user = yield deferToThread(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = None
        yield factory.onNotify(
            mock_class, sentinel.channel, sentinel.action, sentinel.obj_id)
        self.assertIs(
            protocol.cache, mock_class.call_args[0][1])

    @wait_for_reactor
    @inlineCallbacks
    def test_onNotify_calls_handler_class_on_listen(self):
        user = yield deferToThread(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = None
        yield factory.onNotify(
            mock_class, sentinel.channel, sentinel.action, sentinel.obj_id)
        self.assertThat(
            mock_class.return_value.on_listen,
            MockCalledWith(sentinel.channel, sentinel.action, sentinel.obj_id))

    @wait_for_reactor
    def test_onNotify_calls_sendNotify_on_protocol(self):
        user = yield deferToThread(self.make_user)
        protocol, factory = self.make_protocol_with_factory(user=user)
        name = maas_factory.make_name("name")
        action = maas_factory.make_name("action")
        data = maas_factory.make_name("data")
        mock_class = MagicMock()
        mock_class.return_value.on_listen.return_value = (name, data)
        mock_sendNotify = self.patch(protocol, "sendNotify")
        yield factory.onNotify(
            mock_class, sentinel.channel, action, sentinel.obj_id)
        self.assertThat(
            mock_sendNotify, MockCalledWith(name, action, data))
