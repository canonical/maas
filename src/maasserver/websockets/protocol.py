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
from urlparse import (
    parse_qs,
    urlparse,
)

from django.conf import settings
from django.contrib.auth import (
    BACKEND_SESSION_KEY,
    load_backend,
    SESSION_KEY,
)
from django.contrib.auth.models import User
from django.utils.importlib import import_module
from maasserver.eventloop import services
from maasserver.models.nodegroup import NodeGroup
from maasserver.utils.orm import transactional
from maasserver.websockets import handlers
from maasserver.websockets.listener import PostgresListener
from maasserver.websockets.websockets import STATUSES
from provisioningserver.utils.twisted import (
    deferred,
    synchronous,
)
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.protocol import (
    Factory,
    Protocol,
)
from twisted.internet.threads import deferToThreadPool
from twisted.python import log
from twisted.python.threadpool import ThreadPool
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


def get_cookie(cookies, cookie_name):
    """Return the sessionid value from `cookies`."""
    if cookies is None:
        return None
    cookies = SimpleCookie(cookies.encode('utf-8'))
    if cookie_name in cookies:
        return cookies[cookie_name].value
    else:
        return None


class WebSocketProtocol(Protocol):

    def __init__(self, factory):
        self.messages = deque()
        self.factory = factory
        self.user = None
        self.cache = {}

    def connectionMade(self):
        """Connection has been made to client."""
        # Using the provided cookies on the connection request, authenticate
        # the client. If this fails or if the CSRF token can't be found, it
        # will call loseConnection. A websocket connection is only allowed
        # from an authenticated user.
        cookies = self.transport.cookies
        d = self.authenticate(
            get_cookie(cookies, 'sessionid'),
            get_cookie(cookies, 'csrftoken'),
        )

        # Only add the client to the list of known clients if/when the
        # authentication succeeds.
        def add_client(user):
            if user is not None:
                self.factory.clients.append(self)
        d.addCallback(add_client)

    def connectionLost(self, reason):
        """Connection to the client has been lost."""
        # If the connection is lost before the authentication happens, the
        # 'client' will not have been added to the list.
        if self in self.factory.clients:
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

    @deferred
    def authenticate(self, session_id, csrftoken):
        """Authenticate the connection.

        - Check that the CSRF token is valid.
        - Authenticate the user using the session id.
        """
        # Check the CSRF token.
        tokens = parse_qs(
            urlparse(self.transport.uri).query).get('csrftoken')
        if tokens is None or csrftoken not in tokens:
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR, "Invalid CSRF token.")
            return

        # Authenticate user.
        def got_user(user):
            if user is None:
                self.loseConnection(
                    STATUSES.PROTOCOL_ERROR, "Failed to authenticate user.")
                return
            else:
                self.user = user

            self.processMessages()
            return self.user

        def got_user_error(failure):
            self.loseConnection(
                STATUSES.PROTOCOL_ERROR,
                "Error authenticating user: %s" % failure.getErrorMessage())
            return None

        d = deferToThreadPool(
            reactor, self.factory.threadpool,
            self.getUserFromSessionId, session_id)
        d.addCallbacks(got_user, got_user_error)

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

        handler = handler_class(
            self.user, self.cache, self.factory.threadpool)

        d = handler.execute(method, message.get("params", {}))
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
        why = "Error on request (%s) %s.%s: %s" % (
            request_id, handler._meta.handler_name, method, error)
        log.err(failure, _why=why)

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
    """Factory for WebSocketProtocol.

    :ivar threadpool: The thread-pool used for servicing websocket
        requests.
    """

    handlers = {}
    clients = []

    def __init__(self):
        self.threadpool = ThreadPool(name=self.__class__.__name__)
        self.listener = PostgresListener()
        self.cacheHandlers()
        self.registerNotifiers()

    def startFactory(self):
        """Start the thread pool and the listener."""
        self.threadpool.start()
        self.registerRPCEvents()
        return self.listener.start()

    def stopFactory(self):
        """Stop the thread pool and the listener."""
        stopped = self.listener.stop()
        self.unregisterRPCEvents()
        self.threadpool.stop()
        return stopped

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
            handler = handler_class(client.user, client.cache)
            data = yield deferToThreadPool(
                reactor, self.threadpool,
                self.processNotify, handler, channel, action, obj_id)
            if data is not None:
                (name, client_action, data) = data
                client.sendNotify(name, client_action, data)

    @transactional
    def processNotify(self, handler, channel, action, obj_id):
        return handler.on_listen(channel, action, obj_id)

    def buildProtocol(self, addr):
        return WebSocketProtocol(self)

    def registerRPCEvents(self):
        """Register for connected and disconnected events from the RPC
        service."""
        rpc_service = services.getServiceNamed("rpc")
        rpc_service.events.connected.registerHandler(
            self.updateCluster)
        rpc_service.events.disconnected.registerHandler(
            self.updateCluster)

    def unregisterRPCEvents(self):
        """Unregister from connected and disconnected events from the RPC
        service."""
        rpc_service = services.getServiceNamed("rpc")
        rpc_service.events.connected.unregisterHandler(
            self.updateCluster)
        rpc_service.events.disconnected.unregisterHandler(
            self.updateCluster)

    def updateCluster(self, ident):
        """Called when a cluster connects or disconnects from this region
        over the RPC connection.

        This is hard-coded to call the `ClusterHandler` as at the moment
        it is the only handler that needs this event.
        """
        # The `ClusterHandler` expects the `on_listen` call to use the `id`
        # of the `Cluster` object, not the uuid. The `uuid` for the cluster
        # is converted into its `id`, and send to the onNotify call for the
        # `ClusterHandler`.
        d = deferToThreadPool(
            reactor, self.threadpool, self.getCluster, ident)
        d.addCallback(self.sendOnNotifyToCluster)
        d.addErrback(
            log.err,
            "Failed to send 'update' notification for cluster(%s) when "
            "RPC event fired." % ident)
        return d

    @synchronous
    @transactional
    def getCluster(self, cluster_uuid):
        """Return `NodeGroup` with `cluster_uuid`."""
        try:
            return NodeGroup.objects.get(uuid=cluster_uuid)
        except NodeGroup.DoesNotExist:
            return None

    def sendOnNotifyToCluster(self, cluster):
        """Send onNotify to the `ClusterHandler` for `cluster`."""
        cluster_handler = self.getHandler("cluster")
        if cluster_handler is None or cluster is None:
            return
        else:
            return self.onNotify(
                cluster_handler, "cluster", "update", cluster.id)
