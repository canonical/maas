# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Listens for NOTIFY events from the postgres database."""


from collections import defaultdict, deque
from contextlib import contextmanager
from errno import ENOENT
import json
import threading
from typing import Any

from django.db import connection, connections
from django.db.utils import load_backend
from twisted.application.service import Service
from twisted.internet import defer, error, interfaces, reactor, task
from twisted.internet.defer import (
    CancelledError,
    Deferred,
    ensureDeferred,
    succeed,
)
from twisted.internet.task import deferLater
from twisted.internet.threads import deferToThread
from twisted.logger import Logger
from twisted.python.failure import Failure
from zope.interface import implementer

from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.events import EventGroup
from provisioningserver.utils.twisted import callOut, suppress, synchronous


class ACTIONS:
    """Notify action types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class PostgresListenerNotifyError(Exception):
    """Error raised when the listener gets a notify message that cannot be
    decoded or is not being handled."""


class PostgresListenerRegistrationError(Exception):
    """Error raised when registering a handler fails."""


class PostgresListenerUnregistrationError(Exception):
    """Error raised when unregistering a handler fails."""


@implementer(interfaces.IReadDescriptor)
class PostgresListenerService(Service):
    """Listens for NOTIFY messages from postgres.

    A new connection is made to postgres with the isolation level of
    autocommit. This connection is only used for listening for notifications.
    Any query that needs to take place because of a notification should use
    its own connection. This class runs inside of the reactor. Any long running
    action that occurrs based on a notification should defer its action to a
    thread to not block the reactor.

    :ivar connection: A database connection within one of Django's wrapper.
    :ivar connectionFileno: The fileno of the underlying database connection.
    :ivar connecting: a :class:`Deferred` while connecting, `None` at all
        other times.
    :ivar disconnecting: a :class:`Deferred` while disconnecting, `None`
        at all other times.
    """

    # Seconds to wait to handle new notifications. When the notifications set
    # is empty it will wait this amount of time to check again for new
    # notifications.
    HANDLE_NOTIFY_DELAY = 0.5
    CHANNEL_REGISTRAR_DELAY = 0.5

    def __init__(self, alias="default"):
        self.alias = alias
        self.listeners = defaultdict(list)
        self.autoReconnect = False
        self.connection = None
        self.connectionFileno = None
        self.notifications = deque()
        self.notifier = task.LoopingCall(self.handleNotifies)
        self.notifierDone = None
        self.connecting = None
        self.disconnecting = None
        self.shutting_down = False
        self.registeredChannels = set()
        self.channelRegistrar = task.LoopingCall(
            lambda: ensureDeferred(self.registerChannels())
        )
        self.channelRegistrarDone = None
        self.log = Logger(__name__, self)
        self.events = EventGroup("connected", "disconnected")
        # the connection object isn't threadsafe, so we need to lock in order
        # to use it in different threads
        self._db_lock = threading.RLock()

    def startService(self):
        """Start the listener."""
        super().startService()
        self.autoReconnect = True
        self.shutting_down = False
        return self.tryConnection()

    def stopService(self):
        """Stop the listener."""
        super().stopService()
        self.autoReconnect = False
        self.shutting_down = True
        return self.loseConnection()

    def connected(self):
        """Return True if connected."""
        if self.connection is None:
            return False
        if self.connection.connection is None:
            return False
        return self.connection.connection.closed == 0

    def logPrefix(self):
        """Return nice name for twisted logging.

        This is required to satisfy `IReadDescriptor`, which inherits from
        `ILoggingContext`.
        """
        return self.log.namespace

    def isSystemChannel(self, channel):
        """Return True if channel is a system channel."""
        return channel.startswith("sys_")

    def doRead(self):
        """Poll the connection and process any notifications."""
        with self._db_lock:
            try:
                self.connection.connection.poll()
            except Exception:
                # If the connection goes down then `OperationalError` is raised.
                # It contains no pgcode or pgerror to identify the reason so no
                # special consideration can be made for it. Hence all errors are
                # treated the same, and we assume that the connection is broken.
                #
                # We do NOT return a failure, which would signal to the reactor
                # that the connection is broken in some way, because the reactor
                # will end up removing this instance from its list of selectables
                # but not from its list of readable fds, or something like that.
                # The point is that the reactor's accounting gets muddled. Things
                # work correctly if we manage the disconnection ourselves.
                #
                self.loseConnection(Failure(error.ConnectionLost()))
            else:
                self._process_notifies()

    def fileno(self):
        """Return the fileno of the connection."""
        return self.connectionFileno

    def startReading(self):
        """Add this listener to the reactor."""
        self.connectionFileno = self.connection.connection.fileno()
        reactor.addReader(self)

    def stopReading(self):
        """Remove this listener from the reactor."""
        try:
            reactor.removeReader(self)
        except OSError as error:
            # ENOENT here means that the fd has already been unregistered
            # from the underlying poller. It is as yet unclear how we get
            # into this state, so for now we ignore it. See epoll_ctl(2).
            if error.errno != ENOENT:
                raise
        finally:
            self.connectionFileno = None

    def register(self, channel, handler):
        """Register listening for notifications from a channel.

        When a notification is received for that `channel` the `handler` will
        be called with the action and object id.
        """
        if self.shutting_down:
            raise PostgresListenerRegistrationError(
                "Listener service is shutting down."
            )
        self.log.debug(f"Register on {channel} with handler {handler}")
        handlers = self.listeners[channel]
        if self.isSystemChannel(channel) and len(handlers) > 0:
            # A system can only be registered once. This is because the
            # message is passed directly to the handler and the `doRead`
            # method does not wait for it to finish if its a defer. This is
            # different from normal handlers where we will call each and wait
            # for all to resolve before continuing to the next event.
            raise PostgresListenerRegistrationError(
                "System channel '%s' has already been registered." % channel
            )
        else:
            handlers.append(handler)
        self.runChannelRegistrar()

    def unregister(self, channel, handler):
        """Unregister listening for notifications from a channel.

        `handler` needs to be same handler that was registered.
        """
        if self.shutting_down:
            # When shutting down, channels will be unregistered automatically
            self.log.debug(
                f"Unregister on {channel} with handler {handler} skipped due to shutdown"
            )
            return

        self.log.debug(f"Unregister on {channel} with handler {handler}")
        if channel not in self.listeners:
            raise PostgresListenerUnregistrationError(
                "Channel '%s' is not registered with the listener." % channel
            )
        handlers = self.listeners[channel]
        if handler in handlers:
            handlers.remove(handler)
        else:
            raise PostgresListenerUnregistrationError(
                "Handler is not registered on that channel '%s'." % channel
            )
        if len(handlers) == 0:
            # Channels have already been registered. Unregister the channel.
            del self.listeners[channel]
        self.runChannelRegistrar()

    @synchronous
    def createConnection(self):
        """Create new database connection."""
        db = connections.databases[self.alias]
        backend = load_backend(db["ENGINE"])
        return backend.DatabaseWrapper(db, self.alias)

    @synchronous
    def startConnection(self):
        """Start the database connection."""
        self.connection = self.createConnection()
        self.connection.connect()
        self.connection.set_autocommit(True)
        self.connection.inc_thread_sharing()

    @synchronous
    def stopConnection(self):
        """Stop database connection."""
        # The connection is often in an unexpected state here -- for
        # unexplained reasons -- so be careful when unpealing layers.
        connection_wrapper, self.connection = self.connection, None
        if connection_wrapper is not None:
            connection = connection_wrapper.connection
            if connection is not None and not connection.closed:
                connection_wrapper.commit()
                connection_wrapper.close()
                connection_wrapper.dec_thread_sharing()

    def tryConnection(self):
        """Keep retrying to make the connection."""
        if self.connecting is None:
            if self.disconnecting is not None:
                raise RuntimeError(
                    "Cannot attempt to make new connection before "
                    "pending disconnection has finished."
                )

            def cb_connect(_):
                self.log.info("Listening for database notifications.")

            def eb_connect(failure):
                self.log.error(
                    "Unable to connect to database: {error}",
                    error=failure.getErrorMessage(),
                )
                if failure.check(CancelledError):
                    return failure
                elif self.autoReconnect:
                    return deferLater(reactor, 3, connect)
                else:
                    return failure

            def connect(interval=self.HANDLE_NOTIFY_DELAY):
                d = deferToThread(self.startConnection)
                d.addCallback(callOut, self.runChannelRegistrar)
                d.addCallback(lambda result: self.channelRegistrarDone)
                d.addCallback(callOut, self.events.connected.fire)
                d.addCallback(callOut, self.startReading)
                d.addCallback(callOut, self.runHandleNotify, interval)
                # On failure ensure that the database connection is stopped.
                d.addErrback(callOut, deferToThread, self.stopConnection)
                d.addCallbacks(cb_connect, eb_connect)
                return d

            def done():
                self.connecting = None

            self.connecting = connect().addBoth(callOut, done)

        return self.connecting

    def loseConnection(self, reason=Failure(error.ConnectionDone())):
        """Request that the connection be dropped."""
        if self.disconnecting is None:
            self.registeredChannels.clear()
            d = self.disconnecting = Deferred()
            d.addBoth(callOut, self.stopReading)
            d.addBoth(callOut, self.cancelChannelRegistrar)
            d.addBoth(callOut, self.cancelHandleNotify)
            d.addBoth(callOut, deferToThread, self.stopConnection)
            d.addBoth(callOut, self.connectionLost, reason)

            def done():
                self.disconnecting = None
                self.shutting_down = False

            d.addBoth(callOut, done)

            if self.connecting is None:
                # Already/never connected: begin shutdown now.
                self.disconnecting.callback(None)
            else:
                # Still connecting: cancel before disconnect.
                self.connecting.addErrback(suppress, CancelledError)
                self.connecting.chainDeferred(self.disconnecting)
                self.connecting.cancel()

        return self.disconnecting

    def connectionLost(self, reason):
        """Reconnect when the connection is lost."""
        self.connection = None
        if reason.check(error.ConnectionDone):
            self.log.debug("Connection closed.")
        elif reason.check(error.ConnectionLost):
            self.log.debug("Connection lost.")
        else:
            self.log.failure("Connection lost.", reason)
        if self.autoReconnect:
            reactor.callLater(3, self.tryConnection)
        self.events.disconnected.fire(reason)

    def registerChannel(self, channel):
        """Register the channel."""
        self.log.debug(f"Register Channel {channel}")
        with self._db_lock, self.connection.cursor() as cursor:
            if self.isSystemChannel(channel):
                # This is a system channel so listen only called once.
                cursor.execute("LISTEN %s;" % channel)
            else:
                # Not a system channel so listen called once for each action.
                for action in sorted(map_enum(ACTIONS).values()):
                    cursor.execute(f"LISTEN {channel}_{action};")

    def unregisterChannel(self, channel):
        """Unregister the channel."""
        self.log.debug(f"Unregister Channel {channel}")
        with self._db_lock, self.connection.cursor() as cursor:
            if self.isSystemChannel(channel):
                # This is a system channel so unlisten only called once.
                cursor.execute("UNLISTEN %s;" % channel)
            else:
                # Not a system channel so unlisten called once for each action.
                for action in sorted(map_enum(ACTIONS).values()):
                    cursor.execute(f"UNLISTEN {channel}_{action};")

    async def registerChannels(self):
        """Listen/unlisten to channels that were registered/unregistered.

        When a call to register() or unregister() is made, the listeners
        dict is updated, and the keys of that dict represents all the
        channels that we should listen to.

        The service keeps a list of channels that it already listens to
        in the registeredChannels dict. We issue a call to postgres to
        listen to all channels that are in listeners but not in
        registeredChannels, and a call to unlisten for all channels that
        are in registeredChannels but not in listeners.
        """
        to_register = set(self.listeners).difference(self.registeredChannels)
        to_unregister = self.registeredChannels.difference(self.listeners)
        # If there's nothing to do, we can stop the loop. If there is
        # any work to be done, we do the work, and then check
        # whether we should stop at the beginning of the next loop
        # iteration. The reason is that every time we yield, another
        # deferred might call register() or unregister().
        if not to_register and not to_unregister:
            self.channelRegistrar.stop()
        else:
            for channel in to_register:
                await deferToThread(self.registerChannel, channel)
                self.registeredChannels.add(channel)
            for channel in to_unregister:
                await deferToThread(self.unregisterChannel, channel)
                if self.disconnecting:
                    # When disconnecting, registeredChannels will be cleared,
                    # so `remove` will raise `KeyError`. However, we still need
                    # to delete channel from the set if it's there, since the
                    # registration lockout only happens on service shutdown,
                    # which is not the only reason for disconnection.
                    self.registeredChannels.discard(channel)
                else:
                    # In normal operation this shouldn't raise, so if it does,
                    # something unexpected happened.
                    self.registeredChannels.remove(channel)

    def convertChannel(self, channel):
        """Convert the postgres channel to a registered channel and action.

        :raise PostgresListenerNotifyError: When {channel} is not registered or
            {action} is not in `ACTIONS`.
        """
        channel, action = channel.split("_", 1)
        if channel not in self.listeners:
            raise PostgresListenerNotifyError(
                "%s is not a registered channel." % channel
            )
        if action not in map_enum(ACTIONS).values():
            raise PostgresListenerNotifyError(
                "%s action is not supported." % action
            )
        return channel, action

    def runChannelRegistrar(self):
        """Start the loop for listening to channels in postgres.

        It will only start if the service is connected to postgres.
        """
        if self.connection is not None and not self.channelRegistrar.running:
            self.channelRegistrarDone = self.channelRegistrar.start(
                self.CHANNEL_REGISTRAR_DELAY, now=True
            )

    def cancelChannelRegistrar(self):
        """Stop the loop for listening to channels in postgres."""
        if self.channelRegistrar.running:
            self.channelRegistrar.stop()
            return self.channelRegistrarDone
        else:
            return succeed(None)

    def runHandleNotify(self, delay=0, clock=reactor):
        """Defer later the `handleNotify`."""
        if not self.notifier.running:
            self.notifierDone = self.notifier.start(delay, now=False)

    def cancelHandleNotify(self):
        """Cancel the deferred `handleNotify` call."""
        if self.notifier.running:
            self.notifier.stop()
            return self.notifierDone
        else:
            return succeed(None)

    def handleNotifies(self, clock=reactor):
        """Process all notify message in the notifications set."""

        def gen_notifications(notifications):
            while notifications:
                yield notifications.popleft()

        return task.coiterate(
            self.handleNotify(notification, clock=clock)
            for notification in gen_notifications(self.notifications)
        )

    def handleNotify(self, notification, clock=reactor):
        """Process a notify message in the notifications set."""
        channel, payload = notification
        try:
            channel, action = self.convertChannel(channel)
        except PostgresListenerNotifyError:
            # Log the error and continue processing the remaining
            # notifications.
            self.log.failure(
                "Failed to convert channel {channel!r}.", channel=channel
            )
        else:
            defers = []
            handlers = self.listeners[channel]
            # XXX: There could be an arbitrary number of listeners. Should we
            # limit concurrency here? Perhaps even do one at a time.
            for handler in handlers:
                d = defer.maybeDeferred(handler, action, payload)
                d.addErrback(
                    lambda failure: self.log.failure(
                        "Failure while handling notification to {channel!r}: "
                        "{payload!r}",
                        failure,
                        channel=channel,
                        payload=payload,
                    )
                )
                defers.append(d)
            return defer.DeferredList(defers)

    def _process_notifies(self):
        """Add each notify to to the notifications set.

        This removes duplicate notifications when one entity in the database is
        updated multiple times in a short interval. Accumulating notifications
        and allowing the listener to pick them up in batches is imperfect but
        good enough, and simple.

        """
        notifies = self.connection.connection.notifies
        for notify in notifies:
            if self.isSystemChannel(notify.channel):
                # System level message; pass it to the registered
                # handler immediately.
                if notify.channel in self.listeners:
                    # Be defensive in that if a handler does not exist
                    # for this channel then the channel should be
                    # unregisted and removed from listeners.
                    if len(self.listeners[notify.channel]) > 0:
                        handler = self.listeners[notify.channel][0]
                        handler(notify.channel, notify.payload)
                    else:
                        self.unregisterChannel(notify.channel)
                        del self.listeners[notify.channel]
                else:
                    # Unregister the channel since no listener is
                    # registered for this channel.
                    self.unregisterChannel(notify.channel)
            else:
                # Place non-system messages into the queue to be
                # processed.
                notification = (notify.channel, notify.payload)
                if notification not in self.notifications:
                    self.notifications.append(notification)
        # Delete the contents of the connection's notifies list so
        # that we don't process them a second time.
        del notifies[:]

    @contextmanager
    def listen(self, channel, handler):
        """
        Helper for processes that register their channels temporarily
        """
        self.register(channel, handler)
        try:
            yield
        finally:
            self.unregister(channel, handler)


def notify_action(target: str, action: str, identifier: Any):
    """Send a notification for an action on a target."""
    with connection.cursor() as cursor:
        cursor.execute(f"NOTIFY {target}_{action}, %s", [str(identifier)])


def notify(channel: str, payload: Any = None):
    """Send a NOTIFY on the specified channel."""
    with connection.cursor() as cursor:
        cursor.execute(f"NOTIFY {channel}, %s", [json.dumps(payload)])
