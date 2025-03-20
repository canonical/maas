# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS WebSockets protocol."""

from collections import deque
from contextlib import ExitStack
from functools import partial
from http.cookies import SimpleCookie
import ipaddress
import json
from typing import Optional
from urllib.parse import parse_qs, urlparse

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, load_backend, SESSION_KEY
from django.core.exceptions import ValidationError
from django.http import HttpRequest
from django.utils import timezone
from twisted.internet.defer import fail, inlineCallbacks, returnValue, succeed
from twisted.internet.protocol import Factory, Protocol
from twisted.internet.task import LoopingCall
from twisted.python.modules import getModule
from twisted.web.server import NOT_DONE_YET

from maascommon.utils.url import splithost
from maasserver.eventloop import services
from maasserver.utils.orm import transactional
from maasserver.utils.threads import deferToDatabase
from maasserver.websockets import handlers
from maasserver.websockets.websockets import STATUSES
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import synchronous

log = LegacyLogger()


class MSG_TYPE:
    # Request made from client.
    REQUEST = 0

    # Response from server.
    RESPONSE = 1

    # Notify message from server.
    NOTIFY = 2

    # Connectivity checks
    PING = 3
    PING_REPLY = 4


class RESPONSE_TYPE:
    #
    SUCCESS = 0

    #
    ERROR = 1


def get_cookie(cookies: Optional[str], cookie_name: str) -> Optional[str]:
    """Return the sessionid value from `cookies`."""
    if cookies is None:
        return None
    cookies = SimpleCookie(cookies)
    if cookie_name in cookies:
        return cookies[cookie_name].value
    else:
        return None


class WebSocketProtocol(Protocol):
    """The web-socket protocol that supports the web UI.

    :ivar factory: Set by the factory that spawned this protocol.
    """

    def __init__(self):
        self.messages = deque()
        self.user = None
        self.session = None
        self.request = None
        self.cache = {}
        self.sequence_number = 0

    @inlineCallbacks
    def connectionMade(self):
        """Connection has been made to client."""
        # Using the provided cookies on the connection request, authenticate
        # the client. If this fails or if the CSRF token can't be found, it
        # will call loseConnection. A websocket connection is only allowed
        # from an authenticated user.

        cookies = self.transport.cookies.decode("ascii")
        authenticated = yield self.authenticate(
            get_cookie(cookies, "sessionid"), get_cookie(cookies, "csrftoken")
        )
        if not authenticated:
            return

        # XXX newell 2018-10-17 bug=1798479:
        # Check that 'SERVER_NAME' and 'SERVER_PORT' are set.
        # 'SERVER_NAME' and 'SERVER_PORT' are required so
        # `build_absolure_uri` can create an actual absolute URI so
        # that the curtin configuration is valid.  See the bug and
        # maasserver.node_actions for more details.
        #
        # `splithost` will split the host and port from either an
        # ipv4 or an ipv6 address.
        host, port = splithost(str(self.transport.host))

        # Create the request for the handlers for this connection.
        self.request = HttpRequest()
        self.request.user = self.user
        self.request.session = self.session
        self.request.META.update(
            {
                "HTTP_USER_AGENT": self.transport.user_agent,
                "REMOTE_ADDR": self.transport.ip_address,
                "SERVER_NAME": host or "localhost",
                "SERVER_PORT": port or 5248,
            }
        )

        # Be sure to process messages after the metadata is populated,
        # in order to avoid bug #1802390.
        self.processMessages()
        self.factory.clients.append(self)

    def connectionLost(self, reason):
        """Connection to the client has been lost."""
        # If the connection is lost before the authentication happens, the
        # 'client' will not have been added to the list.
        if self in self.factory.clients:
            self.factory.clients.remove(self)

    def loseConnection(self, status, reason):
        """Close connection with status and reason."""
        msgFormat = "Closing connection: {status!r} ({reason!r})"
        log.debug(msgFormat, status=status, reason=reason)
        self.transport.loseConnection(status, reason.encode("utf-8"))

    def getMessageField(self, message, field):
        """Get `field` value from `message`.

        Closes connection with `PROTOCOL_ERROR` if `field` doesn't exist
        in `message`.
        """
        if field not in message:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR,
                f"Missing {field} field in the received message.",
            )
            return None
        return message[field]

    @synchronous
    @transactional
    def get_user_and_session(self, session_id):
        """Return the user and its session from the session ID."""
        session_engine = self.factory.getSessionEngine()
        session = session_engine.SessionStore(session_key=session_id)
        backend = session.get(BACKEND_SESSION_KEY)
        if backend is None:
            return None
        auth_backend = load_backend(backend)
        user_id = session.get(SESSION_KEY)
        if user_id is not None and auth_backend is not None:
            return auth_backend.get_user(user_id), session

        return None

    @inlineCallbacks
    def authenticate(self, session_id, csrftoken):
        """Authenticate the connection.

        - Check that the CSRF token is valid.
        - Authenticate the user using the session id.

        It returns whether authentication succeeded.
        """
        # Check the CSRF token.
        tokens = parse_qs(urlparse(self.transport.uri).query).get(b"csrftoken")
        # Convert tokens from bytes to str as the transport sends it
        # as ascii bytes and the cookie is decoded as unicode.
        if tokens is not None:
            tokens = [token.decode("ascii") for token in tokens]
        if tokens is None or csrftoken not in tokens:
            # No csrftoken in the request or the token does not match.
            self.loseConnection(STATUSES.PROTOCOL_ERROR, "Invalid CSRF token.")
            returnValue(False)
            return

        try:
            result = yield deferToDatabase(
                self.get_user_and_session, session_id
            )
        except Exception as error:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, f"Error authenticating user: {error}"
            )
            returnValue(False)
            return
        if result:
            self.user, self.session = result
        else:
            self.user = self.session = None

        if self.user is None or self.user.id is None:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, "Failed to authenticate user."
            )
            returnValue(False)
        else:
            returnValue(True)

    def dataReceived(self, data):
        """Received message from client and queue up the message."""
        try:
            message = json.loads(data.decode("utf-8"))
        except ValueError:
            # Only accept JSON data over the protocol. Close the connect
            # with invalid data.
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, "Invalid data expecting JSON object."
            )
            return ""
        self.messages.append(message)
        self.processMessages()
        return NOT_DONE_YET

    def processMessages(self):
        """Process all the queued messages."""
        if self.user is None:
            # User is not authenticated yet, don't process messages. Once the
            # user is authenticated this method will be called to process the
            # queued messages.
            return []

        # Process all the messages in the queue.
        handledMessages = []
        while self.messages:
            message = self.messages.popleft()
            handledMessages.append(message)
            msg_type = self.getMessageField(message, "type")
            if msg_type is None:
                return handledMessages
            if msg_type not in (MSG_TYPE.REQUEST, MSG_TYPE.PING):
                # Only support request messages from the client.
                self.loseConnection(
                    STATUSES.PROTOCOL_ERROR, "Invalid message type."
                )
                return handledMessages
            if self.handleRequest(message, msg_type) is None:
                # Handling of request has failed, stop processing the messages
                # in the queue because the connection will be lost.
                return handledMessages
        return handledMessages

    def handleRequest(self, message, msg_type=MSG_TYPE.REQUEST):
        """Handle the request message."""
        # Get the required request_id.
        request_id = self.getMessageField(message, "request_id")
        if request_id is None:
            return None

        if msg_type == MSG_TYPE.PING:
            self.sequence_number += 1
            return succeed(
                self.sendResult(
                    request_id=request_id,
                    result=self.sequence_number,
                    msg_type=MSG_TYPE.PING_REPLY,
                )
            )

        # Decode the method to be called.
        msg_method = self.getMessageField(message, "method")
        if msg_method is None:
            return None
        try:
            handler_name, method = msg_method.split(".", 1)
        except ValueError:
            # Invalid method. Method format is "handler.method".
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, "Invalid method formatting."
            )
            return None

        # Create the handler for the call.
        handler_class = self.factory.getHandler(handler_name)
        if handler_class is None:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR,
                "Handler %s does not exist." % handler_name,
            )
            return None

        handler = self.buildHandler(handler_class)
        d = handler.execute(method, message.get("params", {}))
        d.addCallbacks(
            partial(self.sendResult, request_id),
            partial(self.sendError, request_id, handler, method),
        )
        return d

    def _json_encode(self, obj):
        """
        Encodes specific object types into JSON-compatible formats.

        This method ensures seamless encoding of:
        - Byte strings (`bytes`): Decoded into UTF-8 strings with error handling.
        - IP addresses (`ipaddress.IPv4Address` and `ipaddress.IPv6Address`): Converted to their string representation.

        If the object type is unsupported, a `TypeError` is raised.
        """
        if isinstance(obj, bytes):
            return obj.decode(encoding="utf-8", errors="ignore")
        elif isinstance(obj, ipaddress.IPv4Address) or isinstance(
            obj, ipaddress.IPv6Address
        ):
            return str(obj)
        else:
            raise TypeError("Could not convert object to JSON: %r" % obj)

    def sendResult(self, request_id, result, msg_type=MSG_TYPE.RESPONSE):
        """Send final result to client."""
        result_msg = {
            "type": msg_type,
            "request_id": request_id,
            "rtype": RESPONSE_TYPE.SUCCESS,
            "result": result,
        }
        self.transport.write(
            json.dumps(result_msg, default=self._json_encode).encode("ascii")
        )
        return result

    def sendError(self, request_id, handler, method, failure):
        """Log and send error to client."""
        if isinstance(failure.value, ValidationError):
            try:
                # When the error is a validation issue, send the error as a
                # JSON object. The client will use this to JSON to render the
                # error messages for the correct fields.
                error = json.dumps(failure.value.message_dict)
            except AttributeError:
                error = failure.value.message
        else:
            error = failure.getErrorMessage()
        log.err(
            failure,
            f"Error on request ({request_id}) "
            f"{handler._meta.handler_name}.{method}: {error}",
        )

        error_msg = {
            "type": MSG_TYPE.RESPONSE,
            "request_id": request_id,
            "rtype": RESPONSE_TYPE.ERROR,
            "error": error,
        }
        self.transport.write(
            json.dumps(error_msg, default=self._json_encode).encode("ascii")
        )
        return None

    def sendNotify(self, name, action, data):
        """Send the notify message with data."""
        notify_msg = {
            "type": MSG_TYPE.NOTIFY,
            "name": name,
            "action": action,
            "data": data,
        }
        self.transport.write(
            json.dumps(notify_msg, default=self._json_encode).encode("ascii")
        )

    def buildHandler(self, handler_class):
        """Return an initialised instance of `handler_class`."""
        handler_name = handler_class._meta.handler_name
        handler_cache = self.cache.setdefault(handler_name, {})
        session_id = self.session.session_key
        return handler_class(
            self.user, handler_cache, self.request, session_id
        )


class WebSocketFactory(Factory):
    """Factory for WebSocketProtocol."""

    protocol = WebSocketProtocol

    def __init__(self, listener):
        self.handlers = {}
        self.clients = []
        self.listener = listener
        self.session_checker = LoopingCall(self._check_sessions)
        self.session_checker_done = None
        self.cacheHandlers()
        self.registerNotifiers()

    def startFactory(self):
        self._cleanup_stack = ExitStack()
        self.registerRPCEvents()
        self._cleanup_stack.callback(self.unregisterRPCEvents)
        self.session_checker_done = self.session_checker.start(5, now=True)
        self._cleanup_stack.callback(self.session_checker.stop)

    def stopFactory(self):
        self._cleanup_stack.close()

    def getSessionEngine(self):
        """Returns the session engine being used by Django.

        Used by the protocol to validate the sessionid.
        """
        return getModule(settings.SESSION_ENGINE).load()

    def cacheHandlers(self):
        """Cache all the websocket handlers."""
        for name in dir(handlers):
            # Ignore internals
            if name.startswith("_"):
                continue
            # Only care about class that have _meta attribute, as that
            # means its a handler.
            cls = getattr(handlers, name)
            if not hasattr(cls, "_meta"):
                continue
            meta = cls._meta
            # Skip over abstract handlers as they only provide helpers for
            # children classes and should not be exposed over the channel.
            if meta.abstract:
                continue
            if (
                meta.handler_name is not None
                and meta.handler_name not in self.handlers
            ):
                self.handlers[meta.handler_name] = cls

    def getHandler(self, name):
        """Return handler by name from the handler cache."""
        return self.handlers.get(name)

    def registerNotifiers(self):
        """Registers all of the postgres channels in the handlers."""
        for handler in self.handlers.values():
            for channel in handler._meta.listen_channels:
                self.listener.register(
                    channel, partial(self.onNotify, handler, channel)
                )

    @inlineCallbacks
    def onNotify(self, handler_class, channel, action, obj_id):
        for client in self.clients:
            handler = client.buildHandler(handler_class)
            data = yield deferToDatabase(
                self.processNotify, handler, channel, action, obj_id
            )
            if data is not None:
                (name, client_action, data) = data
                client.sendNotify(name, client_action, data)

    @transactional
    def processNotify(self, handler, channel, action, obj_id):
        return handler.on_listen(channel, action, obj_id)

    def registerRPCEvents(self):
        """Register for connected and disconnected events from the RPC
        service."""
        rpc_service = services.getServiceNamed("rpc")
        rpc_service.events.connected.registerHandler(self.updateRackController)
        rpc_service.events.disconnected.registerHandler(
            self.updateRackController
        )

    def unregisterRPCEvents(self):
        """Unregister from connected and disconnected events from the RPC
        service."""
        rpc_service = services.getServiceNamed("rpc")
        rpc_service.events.connected.unregisterHandler(
            self.updateRackController
        )
        rpc_service.events.disconnected.unregisterHandler(
            self.updateRackController
        )

    def updateRackController(self, ident):
        """Called when a rack controller connects or disconnects from this
        region over the RPC connection.

        This is hard-coded to call the `ControllerHandler` as at the moment
        it is the only handler that needs this event.
        """
        d = self.sendOnNotifyToController(ident)
        d.addErrback(
            log.err,
            f"Failed to send 'update' notification for rack controller({ident}) "
            "when RPC event fired.",
        )
        return d

    def sendOnNotifyToController(self, system_id):
        """Send onNotify to the `ControllerHandler` for `system_id`."""
        rack_handler = self.getHandler("controller")
        if rack_handler:
            return self.onNotify(
                rack_handler, "controller", "update", system_id
            )
        else:
            return fail("Unable to get the 'controller' handler.")

    @inlineCallbacks
    def _check_sessions(self):
        client_sessions = {
            client.session.session_key: client
            for client in self.clients
            if client.session is not None
        }
        client_session_keys = set(client_sessions)

        def get_valid_sessions(session_keys):
            session_engine = self.getSessionEngine()
            Session = session_engine.SessionStore.get_model_class()
            return set(
                Session.objects.filter(
                    session_key__in=session_keys,
                    expire_date__gt=timezone.now(),
                ).values_list("session_key", flat=True)
            )

        valid_session_keys = yield deferToDatabase(
            get_valid_sessions,
            client_session_keys,
        )
        # drop connections for expired sessions
        for session_key in client_session_keys - valid_session_keys:
            if client := client_sessions.get(session_key):
                client.loseConnection(STATUSES.NORMAL, "Session expired")

        returnValue(None)
