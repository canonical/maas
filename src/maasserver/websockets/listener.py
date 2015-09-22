# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Listens for NOTIFY events from the postgres database."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    ]

from collections import defaultdict
from contextlib import closing

from django.db import connections
from django.db.utils import load_backend
from maasserver.utils.threads import deferToDatabase
from provisioningserver.utils.enum import map_enum
from provisioningserver.utils.twisted import synchronous
from psycopg2 import OperationalError
from twisted.internet import (
    defer,
    error,
    interfaces,
    reactor,
    task,
)
from twisted.python import (
    failure,
    log,
)
from zope.interface import implements


class ACTIONS:
    """Notify action types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"


class PostgresListenerNotifyError(Exception):
    """Error raised when the listener gets a notify message that cannot be
    decoded or is not being handled."""


class PostgresListener:
    """Listens for NOTIFY messages from postgres.

    A new connection is made to postgres with the isolation level of
    autocommit. This connection is only used for listening for notifications.
    Any query that needs to take place because of a notification should use
    its own connection. This class runs inside of the reactor. Any long running
    action that occurrs based on a notification should defer its action to a
    thread to not block the reactor.
    """

    implements(interfaces.IReadDescriptor)

    # Seconds to wait to handle new notifications. When the notifications set
    # is empty it will wait this amount of time to check again for new
    # notifications.
    HANDLE_NOTIFY_DELAY = 0.5

    def __init__(self, alias="default"):
        self.alias = alias
        self.listeners = defaultdict(list)
        self.autoReconnect = False
        self.connection = None
        self.notifications = set()
        self.notifier = task.LoopingCall(self.handleNotifies)

    def start(self):
        """Start the listener."""
        self.autoReconnect = True
        return self.tryConnection()

    def stop(self):
        """Stop the listener."""
        self.autoReconnect = False
        reactor.removeReader(self)
        self.cancelHandleNotify()
        return deferToDatabase(self.stopConnection)

    def connected(self):
        """Return True if connected."""
        if self.connection is None:
            return False
        if self.connection.connection is None:
            return False
        return self.connection.connection.closed == 0

    def logPrefix(self):
        """Return nice name for twisted logging."""
        return "maas.websocket.listener"

    def logMsg(self, *args, **kwargs):
        """Helper to log message with the correct logPrefix."""
        kwargs['system'] = self.logPrefix()
        log.msg(*args, **kwargs)

    def logErr(self, *args, **kwargs):
        """Helper to log error with the correct logPrefix."""
        kwargs['system'] = self.logPrefix()
        log.err(*args, **kwargs)

    def fileno(self):
        """Return the fileno of the connection.

        If the connection is not open, return `None`.
        """
        # The connection is often in an unexpected state here -- for
        # unexplained reasons -- so be careful when unpealing layers.
        connection_wrapper = self.connection
        if connection_wrapper is None:
            return None
        else:
            connection = connection_wrapper.connection
            if connection is None:
                return None
            elif connection.closed:
                return None
            else:
                return connection.fileno()

    def doRead(self):
        """Poll the connection and process any notifications."""
        try:
            self.connection.connection.poll()
        except OperationalError:
            # If the connection goes down then this exception is raised. It
            # contains no pgcode or pgerror to identify the reason, so best
            # assumtion is that the connection has been lost.
            reactor.removeReader(self)
            self.cancelHandleNotify()
            self.connectionLost(failure.Failure(error.ConnectionClosed()))
        else:
            # Add each notify to to the notifications set. This helps
            # removes duplicate notifications as one entity in the database
            # can send multiple notifies as it can be updated quickly.
            # Accumulate the notifications and the listener passes them on to
            # be handled in batches.
            notifies = self.connection.connection.notifies
            if len(notifies) != 0:
                for notify in notifies:
                    self.notifications.add((notify.channel, notify.payload))
                # Delete the contents of the connection's notifies list so
                # that we don't process them a second time.
                del notifies[:]

    def connectionLost(self, reason):
        """Reconnect when the connection is lost."""
        if not self.autoReconnect:
            # Do nothing. No need to reconnect to the database.
            return

        # Try to reconnect to the database.
        self.connection = None
        self.tryConnection()

    def register(self, channel, handler):
        """Register listening for notifications from a channel.

        When a notification is received for that `channel` the `handler` will
        be called with the action and object id.
        """
        self.listeners[channel].append(handler)

    @synchronous
    def createConnection(self):
        """Create new database connection."""
        db = connections.databases[self.alias]
        backend = load_backend(db['ENGINE'])
        return backend.DatabaseWrapper(
            db, self.alias, allow_thread_sharing=True)

    @synchronous
    def startConnection(self):
        """Start the database connection."""
        self.connection = self.createConnection()
        self.connection.connect()
        self.connection.enter_transaction_management()
        self.connection.set_autocommit(True)

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
                connection_wrapper.leave_transaction_management()
                connection_wrapper.close()

    def tryConnection(self):
        """Keep retrying to make the connection."""

        def failureToConnect(failure):
            msgFormat = "Unable to connect to database: %(error)r"
            self.logMsg(format=msgFormat, error=failure.getErrorMessage())
            # XXX: Consider using `return deferLater(...)` here, so that
            # callers don't lose a handle on what's happening.
            reactor.callLater(3, self.tryConnection)

        d = deferToDatabase(self.startConnection)
        d.addCallback(lambda _: deferToDatabase(self.registerChannels))
        d.addCallback(lambda _: reactor.addReader(self))
        d.addCallback(
            lambda _: self.runHandleNotify(delay=self.HANDLE_NOTIFY_DELAY))
        d.addCallback(
            lambda _: self.logMsg("Listening for notificaton from database."))
        d.addErrback(failureToConnect)
        return d

    def registerChannels(self):
        """Register the all the channels."""
        for channel in self.listeners.keys():
            with closing(self.connection.cursor()) as cursor:
                for action in map_enum(ACTIONS).values():
                    cursor.execute("LISTEN %s_%s;" % (channel, action))

    def convertChannel(self, channel):
        """Convert the postgres channel to a registered channel and action.

        The postgres channel is structured as {channel}_{action}. This is split
        to match the correct handler and action for that handler.

        :raise PostgresListenerNotifyError: When {channel} is not registered or
            {action} is not in `ACTIONS`.
        """
        channel, action = channel.split('_', 1)
        if channel not in self.listeners:
            raise PostgresListenerNotifyError(
                "%s is not a registered channel." % channel)
        if action not in map_enum(ACTIONS).values():
            raise PostgresListenerNotifyError(
                "%s action is not supported." % action)
        return channel, action

    def runHandleNotify(self, delay=0, clock=reactor):
        """Defer later the `handleNotify`."""
        if not self.notifier.running:
            self.notifier.start(delay, now=False)

    def cancelHandleNotify(self):
        """Cancel the deferred `handleNotify` call."""
        if self.notifier.running:
            self.notifier.stop()

    def handleNotifies(self, clock=reactor):
        """Process all notify message in the notifications set."""
        def gen_notifications(notifications):
            while len(notifications) != 0:
                yield notifications.pop()
        return task.coiterate(
            self.handleNotify(notification, clock=clock)
            for notification in gen_notifications(self.notifications))

    def handleNotify(self, notification, clock=reactor):
        """Process a notify message in the notifications set."""
        channel, payload = notification
        try:
            channel, action = self.convertChannel(channel)
        except PostgresListenerNotifyError as e:
            # Log the error and continue processing the remaining
            # notifications.
            self.logErr(e)
        else:
            defers = []
            handlers = self.listeners[channel]
            for handler in handlers:
                d = defer.maybeDeferred(handler, action, payload)
                d.addErrback(self.logErr)
                defers.append(d)
            return defer.DeferredList(defers)
