# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS WebSockets protocol."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

from collections import deque
from Cookie import SimpleCookie
from functools import partial
import json

from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    load_backend,
    SESSION_KEY,
    )
from django.contrib.auth.models import User
from django.utils.importlib import import_module
from maasserver.utils.orm import transactional
from maasserver.websockets import handlers
from maasserver.websockets.listener import PostgresListener
from maasserver.websockets.websockets import STATUSES
from provisioningserver.utils.twisted import synchronous
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import (
    Factory,
    Protocol,
    )
from twisted.internet.threads import deferToThread
from twisted.python import log
from twisted.web.server import NOT_DONE_YET


class MSG_TYPE:
    #: Request made from client.
    REQUEST = 0

    #: Response from server.
    RESPONSE = 1

    #: Notify message from server.
    NOTIFY = 2


class RESPONSE_TYPE:
    #:
    SUCCESS = 0

    #:
    ERROR = 1


def get_sessionid(cookies):
    """Return the sessionid value from `cookies`."""
    if cookies is None:
        return None
    cookies = SimpleCookie(cookies.encode('utf-8'))
    if "sessionid" in cookies:
        return cookies["sessionid"].value
    else:
        return None


class WebSocketProtocol(Protocol):

    def __init__(self, factory):
        self.messages = deque()
        self.factory = factory
        self.user = None

    def connectionMade(self):
        """Connection has been made to client."""
        self.factory.clients.append(self)

        # Using the provided cookies on the connection request, authenticate
        # the client. If this fails it will call loseConnection. A websocket
        # connection is only allowed from an authenticated user.
        self.authenticate(
            get_sessionid(self.transport.cookies))

    def connectionLost(self, reason):
        """Connection to the client has been lost."""
        self.factory.clients.remove(self)

    def loseConnection(self, status, reason):
        """Close connection with status and reason."""
        msgFormat = "Closing connection: %(status)r (%(reason)r)"
        log.msg(format=msgFormat, status=status, reason=reason)
        self.transport._receiver._transport.loseConnection(
            status, reason.encode("utf-8"))

    def getMessageField(self, message, field):
        """Get `field` value from `message`.

        Closes connection with `PROTOCOL_ERROR` if `field` doesn't exist
        in `message`.
        """
        if field not in message:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR,
                "Missing %s field in the received message." % field)
            return None
        return message[field]

    @synchronous
    @transactional
    def getUserFromSessionId(self, session_id):
        """Return the user from `session_id`."""
        session_engine = self.factory.getSessionEngine()
        session_wrapper = session_engine.SessionStore(session_id)
        user_id = session_wrapper.get(SESSION_KEY)
        backend = session_wrapper.get(BACKEND_SESSION_KEY)
        if backend is None:
            return None
        auth_backend = load_backend(backend)
        if user_id is not None and auth_backend is not None:
            user = auth_backend.get_user(user_id)
            # Get the user again prefetching the SSHKey for the user. This is
            # done so a query is not made for each action that is possible on
            # a node in the node listing.
            return User.objects.filter(
                id=user.id).prefetch_related('sshkey_set').first()
        else:
            return None

    def authenticate(self, session_id):
        """Authenticate the connection."""

        def got_user(user):
            if user is None:
                self.loseConnection(
                    STATUSES.PROTOCOL_ERROR, "Failed to authenticate user.")
            else:
                self.user = user
            self.processMessages()

        def got_error(failure):
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR,
                "Error authenticating user: %s" % failure.getErrorMessage())
            return None

        d = deferToThread(self.getUserFromSessionId, session_id)
        d.addCallbacks(got_user, got_error)
        return d

    def dataReceived(self, data):
        """Received message from client and queue up the message."""
        try:
            message = json.loads(data)
        except ValueError:
            # Only accept JSON data over the protocol. Close the connect
            # with invalid data.
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, "Invalid data expecting JSON object.")
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
        while len(self.messages) > 0:
            message = self.messages.popleft()
            handledMessages.append(message)
            msg_type = self.getMessageField(message, "type")
            if msg_type is None:
                return handledMessages
            if msg_type != MSG_TYPE.REQUEST:
                # Only support request messages from the client.
                self.loseConnection(
                    STATUSES.PROTOCOL_ERROR, "Invalid message type.")
                return handledMessages
            if self.handleRequest(message) is None:
                # Handling of request has failed, stop processing the messages
                # in the queue because the connection will be lost.
                return handledMessages
        return handledMessages

    def handleRequest(self, message):
        """Handle the request message."""
        # Get the required request_id.
        request_id = self.getMessageField(message, "request_id")
        if request_id is None:
            return None

        # Decode the method to be called.
        msg_method = self.getMessageField(message, "method")
        if msg_method is None:
            return None
        try:
            handler_name, method = msg_method.split(".", 1)
        except ValueError:
            # Invalid method. Method format is "handler.method".
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, "Invalid method formatting.")
            return None

        # Create the handler for the call.
        handler_class = self.factory.getHandler(handler_name)
        if handler_class is None:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR,
                "Handler %s does not exist." % handler_name)
            return None
        handler = handler_class(self.user)

        # Wrap the handler.execute method in transactional. This will insure
        # the retry logic is performed and that any post_commit will be
        # performed. The execution of this method is defered to a thread
        # because it interacts with the database which is blocking.
        transactional_execute = transactional(handler.execute)
        d = deferToThread(
            transactional_execute, method, message.get("params", {}))
        d.addCallbacks(
            partial(self.sendResult, request_id),
            partial(self.sendError, request_id, handler, method))
        return d

    def sendResult(self, request_id, result):
        """Send final result to client."""
        result_msg = {
            "type": MSG_TYPE.RESPONSE,
            "request_id": request_id,
            "rtype": RESPONSE_TYPE.SUCCESS,
            "result": result,
            }
        self.transport.write(json.dumps(result_msg).encode("utf-8"))
        return result

    def sendError(self, request_id, handler, method, failure):
        """Log and send error to client."""
        error = failure.getErrorMessage()
        msgFormat = (
            "Error on request (%(request_id)r) "
            "%(handler)r.%(method)r: %(error)r")
        log.msg(
            format=msgFormat, request_id=request_id,
            handler=handler._meta.handler_name, method=method, error=error)

        error_msg = {
            "type": MSG_TYPE.RESPONSE,
            "request_id": request_id,
            "rtype": RESPONSE_TYPE.ERROR,
            "error": error,
            }
        self.transport.write(json.dumps(error_msg).encode("utf-8"))
        return None

    def sendNotify(self, name, action, data):
        """Send the notify message with data."""
        notify_msg = {
            "type": MSG_TYPE.NOTIFY,
            "name": name,
            "action": action,
            "data": data,
            }
        self.transport.write(json.dumps(notify_msg).encode("utf-8"))


class WebSocketFactory(Factory):

    handlers = {}
    clients = []

    def __init__(self):
        self.listener = PostgresListener()
        self.cacheHandlers()
        self.registerNotifiers()

    def startFactory(self):
        """Start the listener."""
        return self.listener.start()

    def stopFactory(self):
        """Stop the listener."""
        return self.listener.stop()

    def getSessionEngine(self):
        """Returns the session engine being used by Django.

        Used by the protocol to validate the sessionid.
        """
        return import_module(settings.SESSION_ENGINE)

    def cacheHandlers(self):
        """Cache all the websocket handlers."""
        for name in dir(handlers):
            # Ignore internals
            if name.startswith("_"):
                continue
            # Only care about class that have _meta attribute, as that
            # means its a handler.
            cls = getattr(handlers, name)
            if not hasattr(cls, '_meta'):
                continue
            meta = cls._meta
            # Skip over abstract handlers as they only provide helpers for
            # children classes and should not be exposed over the channel.
            if meta.abstract:
                continue
            if (meta.handler_name is not None and
                    meta.handler_name not in self.handlers):
                self.handlers[meta.handler_name] = cls

    def getHandler(self, name):
        """Return handler by name from the handler cache."""
        return self.handlers.get(name)

    def registerNotifiers(self):
        """Registers all of the postgres channels in the handlers."""
        for handler in self.handlers.values():
            for channel in handler._meta.listen_channels:
                self.listener.register(
                    channel, partial(self.onNotify, handler, channel))

    @inlineCallbacks
    def onNotify(self, handler_class, channel, action, obj_id):
        for client in self.clients:
            handler = handler_class(client.user)
            data = yield deferToThread(
                self.processNotify, handler, channel, action, obj_id)
            if data is not None:
                (name, data) = data
                client.sendNotify(name, action, data)

    @transactional
    def processNotify(self, handler, channel, action, obj_id):
        return handler.on_listen(channel, action, obj_id)

    def buildProtocol(self, addr):
        return WebSocketProtocol(self)
