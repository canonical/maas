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
from twisted.internet.threads import deferToThread
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

    def __init__(self, alias="default"):
        self.alias = alias
        self.listeners = defaultdict(list)
        self.autoReconnect = False
        self.connection = None

    def start(self):
        """Start the listener."""
        self.autoReconnect = True
        return self.tryConnection()

    def stop(self):
        """Stop the listener."""
        self.autoReconnect = False
        if self.connected():
            reactor.removeReader(self)
            return deferToThread(self.stopConnection)
        else:
            return defer.succeed(None)

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
        """Return the fileno of the connection."""
        return self.connection.connection.fileno()

    def doRead(self):
        """Poll the connection and process any notifications."""
        try:
            self.connection.connection.poll()
        except OperationalError:
            # If the connection goes down then this exception is raised. It
            # contains no pgcode or pgerror to identify the reason, so best
            # assumtion is that the connection has been lost. Exit early.
            return self.connectionLost(
                failure.Failure(error.ConnectionClosed()))

        # Process all of the notify messages inside of a Cooperator so each
        # notification will be handled in order.
        if self.connection.connection.notifies:
            task.cooperate(self.handleNotifies())

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
        self.connection.commit()
        self.connection.leave_transaction_management()
        self.connection.close()

    def tryConnection(self):
        """Keep retrying to make the connection."""

        def failureToConnect(failure):
            msgFormat = "Unable to connect to database: %(error)r"
            self.logMsg(format=msgFormat, error=failure.getErrorMessage())
            reactor.callLater(3, self.tryConnection)

        d = deferToThread(self.startConnection)
        d.addCallback(lambda _: deferToThread(self.registerChannels))
        d.addCallback(lambda _: reactor.addReader(self))
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

    def handleNotifies(self):
        """Process each notify message yeilding to the returned defer.

        This method should be called from the global Cooperator so each notify
        message is handled in order.
        """
        for notify in self.connection.connection.notifies:
            try:
                channel, action = self.convertChannel(notify.channel)
            except PostgresListenerNotifyError as e:
                # Log the error and continue processing the remaining
                # notifications.
                self.logErr(e)
            else:
                handlers = self.listeners[channel]
                for handler in handlers:
                    yield defer.maybeDeferred(
                        handler, action, notify.payload).addErrback(
                        self.logErr)

        del self.connection.connection.notifies[:]
