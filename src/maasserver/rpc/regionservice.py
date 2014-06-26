# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""RPC implementation for regions."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "RegionService",
    "RegionAdvertisingService",
]

from collections import defaultdict
from contextlib import closing
import random
from textwrap import dedent
import threading

from crochet import reactor
from django.db import connection
from maasserver import (
    eventloop,
    locks,
    )
from maasserver.rpc import (
    bootsources,
    configuration,
    )
from maasserver.utils import synchronised
from maasserver.utils.async import transactional
from provisioningserver.rpc import (
    cluster,
    common,
    exceptions,
    region,
    )
from provisioningserver.rpc.interfaces import IConnection
from provisioningserver.utils import (
    asynchronous,
    synchronous,
    )
from provisioningserver.utils.network import get_all_interface_addresses
from twisted.application import service
from twisted.application.internet import TimerService
from twisted.internet import (
    defer,
    ssl,
    )
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.internet.threads import deferToThread
from twisted.protocols import amp
from twisted.python import (
    filepath,
    log,
    )
from zope.interface import implementer


class Region(amp.AMP):
    """The RPC protocol supported by a region controller.

    This can be used on the client or server end of a connection; once a
    connection is established, AMP is symmetric.
    """

    @region.Identify.responder
    def identify(self):
        """identify()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.Identify`.
        """
        return {b"ident": eventloop.loop.name}

    @region.ReportBootImages.responder
    def report_boot_images(self, uuid, images):
        """report_boot_images(uuid, images)

        Implementation of
        :py:class:`~provisioningserver.rpc.region.ReportBootImages`.
        """
        return {}

    @amp.StartTLS.responder
    def get_tls_parameters(self):
        """get_tls_parameters()

        Implementation of :py:class:`~twisted.protocols.amp.StartTLS`.
        """
        # TODO: Obtain certificates from a config store.
        testing = filepath.FilePath(__file__).sibling("testing")
        with testing.child("region.crt").open() as fin:
            tls_localCertificate = ssl.PrivateCertificate.loadPEM(fin.read())
        with testing.child("trust.crt").open() as fin:
            tls_verifyAuthorities = [
                ssl.Certificate.loadPEM(fin.read()),
            ]
        return {
            "tls_localCertificate": tls_localCertificate,
            "tls_verifyAuthorities": tls_verifyAuthorities,
        }

    @region.GetBootSources.responder
    def get_boot_sources(self, uuid):
        """get_boot_sources()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetBootSources`.
        """
        d = deferToThread(bootsources.get_boot_sources, uuid)
        d.addCallback(lambda sources: {b"sources": sources})
        return d

    @region.GetProxies.responder
    def get_proxies(self):
        """get_proxies()

        Implementation of
        :py:class:`~provisioningserver.rpc.region.GetProxies`.
        """
        d = deferToThread(configuration.get_proxies)
        return d


@implementer(IConnection)
class RegionServer(Region):
    """The RPC protocol supported by a region controller, server version.

    This works hand-in-hand with ``RegionService``, maintaining the
    latter's ``connections`` set.

    :ivar factory: Reference to the factory that made this, set by the
        factory. The factory must also have a reference back to the
        service that created it.

    :ivar ident: The identity (e.g. UUID) of the remote cluster.
    """

    factory = None
    ident = None

    def connectionMade(self):
        super(RegionServer, self).connectionMade()
        if self.factory.service.running:
            d = self.callRemote(cluster.Identify)

            def cb_identify(response):
                self.ident = response.get("ident")
                self.factory.service.connections[self.ident].add(self)

            def eb_identify(failure):
                log.err(failure)
                return self.transport.loseConnection()

            d.addCallbacks(cb_identify, eb_identify)
        else:
            self.transport.loseConnection()

    def connectionLost(self, reason):
        self.factory.service.connections[self.ident].discard(self)
        super(RegionServer, self).connectionLost(reason)


class RegionService(service.Service, object):
    """A region controller RPC service.

    This is a service - in the Twisted sense - that exposes the
    ``Region`` protocol on a port.

    :ivar connections: A set of :class:`Region` connections to clusters.

    :ivar starting: Either `None`, or a :class:`Deferred` that fires
        with the port that's been opened, or the error that prevented it
        from opening.
    """

    connections = None
    starting = None

    def __init__(self):
        super(RegionService, self).__init__()
        self.endpoint = TCP4ServerEndpoint(reactor, 0)
        self.connections = defaultdict(set)
        self.factory = Factory.forProtocol(RegionServer)
        self.factory.service = self
        self._port = None

    @asynchronous
    def startService(self):
        """Start listening on an ephemeral port."""
        super(RegionService, self).startService()
        self.starting = self.endpoint.listen(self.factory)

        def save_port(port):
            self._port = port
            return port
        self.starting.addCallback(save_port)

        def ignore_cancellation(failure):
            failure.trap(defer.CancelledError)
        self.starting.addErrback(ignore_cancellation)

        self.starting.addErrback(log.err)

    @asynchronous
    @inlineCallbacks
    def stopService(self):
        """Stop listening."""
        self.starting.cancel()
        if self._port is not None:
            yield self._port.stopListening()
        for conns in self.connections.itervalues():
            for conn in conns:
                try:
                    yield conn.transport.loseConnection()
                except:
                    log.err()
        yield super(RegionService, self).stopService()

    @asynchronous
    def getPort(self):
        """Return the port on which this service is listening.

        `None` if the port has not yet been opened.
        """
        try:
            socket = self._port.socket
        except AttributeError:
            # self._port might be None, or self._port.socket may not yet
            # be set; either implies that there is no connection.
            return None
        else:
            host, port = socket.getsockname()
            return port

    @asynchronous
    def getClientFor(self, uuid):
        """Return a :class:`common.Client` for the specified cluster.

        If more than one connection exists to that cluster - implying
        that there are multiple cluster controllers for the particular
        cluster, for HA - one of them will be returned at random.

        :param uuid: The UUID - as a string - of the cluster that a
            connection is wanted for.
        :raises exceptions.NoConnectionsAvailable: When no connection to the
            given cluster is available.
        """
        conns = list(self.connections[uuid])
        if len(conns) == 0:
            raise exceptions.NoConnectionsAvailable()
        else:
            return common.Client(random.choice(conns))

    @asynchronous
    def getAllClients(self):
        """Return a list of all connected :class:`common.Client`s."""
        return [
            common.Client(conn)
            for conns in self.connections.itervalues()
            for conn in conns
        ]


class RegionAdvertisingService(TimerService, object):
    """Advertise the local event-loop to all other event-loops.

    This implementation uses an unlogged table in PostgreSQL.

    :cvar lock: A lock to help coordinate - and prevent - concurrent
        database access from this service across the whole interpreter.

    :ivar starting: Either `None`, or a :class:`Deferred` that fires
        with the service has successfully started. It does *not*
        indicate that the first update has been done.

    """

    # Django defaults to read committed isolation, but this is not
    # enough for `update()`. Writing a decent wrapper to get it to use
    # serializable isolation for a single transaction is difficult; it
    # looks like Django squashes psycopg2's TransactionRollbackError
    # into IntegrityError, which is overly broad. We're concerned only
    # about concurrent access from this process (other processes will
    # not conflict), so a thread-lock is a sufficient workaround.
    lock = threading.Lock()

    starting = None
    stopping = None

    def __init__(self, interval=60):
        super(RegionAdvertisingService, self).__init__(
            interval, deferToThread, self.update)

    @asynchronous
    def startService(self):
        self.starting = deferToThread(self.prepare)
        self.starting.addCallback(lambda ignore: (
            super(RegionAdvertisingService, self).startService()))

        def ignore_cancellation(failure):
            failure.trap(defer.CancelledError)
        self.starting.addErrback(ignore_cancellation)

        self.starting.addErrback(log.err)
        return self.starting

    @asynchronous
    def stopService(self):
        if self.starting.called:
            # Start-up is complete; remove all records then up-call in
            # the usual way.
            self.stopping = deferToThread(self.remove)
            self.stopping.addCallback(lambda ignore: (
                super(RegionAdvertisingService, self).stopService()))
            return self.stopping
        else:
            # Start-up has not yet finished; cancel it.
            self.starting.cancel()
            return self.starting

    @synchronous
    @synchronised(lock)
    @transactional
    @synchronised(locks.eventloop)
    def prepare(self):
        """Ensure that the ``eventloops`` table exists.

        If not, create it. It is not managed by Django's ORM - though
        this borrows Django's database connection code - because using
        database-specific features like unlogged tables is hard work
        with Django (and South).

        The ``eventloops`` table contains an address and port where each
        event-loop in a region is listening. Each record also contains a
        timestamp so that old records can be erased.
        """
        with closing(connection.cursor()) as cursor:
            self._do_create(cursor)

    @synchronous
    @synchronised(lock)
    @transactional
    def update(self):
        """Repopulate the ``eventloops`` with this process's information.

        It updates all the records in ``eventloops`` related to the
        event-loop running in the same process, and deletes - garbage
        collects - old records related to any event-loop.
        """
        with closing(connection.cursor()) as cursor:
            self._do_delete(cursor)
            self._do_insert(cursor)
            self._do_collect(cursor)

    @synchronous
    @synchronised(lock)
    @transactional
    def dump(self):
        """Returns a list of ``(name, addr, port)`` tuples.

        Each tuple corresponds to somewhere an event-loop is listening
        within the whole region. The `name` is the event-loop name.
        """
        with closing(connection.cursor()) as cursor:
            self._do_select(cursor)
            return list(cursor)

    @synchronous
    @synchronised(lock)
    @transactional
    def remove(self):
        """Removes all records related to this event-loop.

        A subsequent call to `update()` will restore these records,
        hence calling this while this service is started won't be
        terribly efficacious.
        """
        with closing(connection.cursor()) as cursor:
            self._do_delete(cursor)

    def _get_addresses(self):
        try:
            service = eventloop.services.getServiceNamed("rpc")
        except KeyError:
            pass  # No RPC service yet.
        else:
            port = service.getPort().wait(5)
            if port is not None:
                for addr in get_all_interface_addresses():
                    yield addr, port

    _create_statement = dedent("""\
      CREATE UNLOGGED TABLE IF NOT EXISTS eventloops (
        name          TEXT NOT NULL,
        address       INET NOT NULL,
        port          INTEGER NOT NULL,
        updated       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        CHECK (port > 0 AND port <= 65535),
        UNIQUE (name, address, port),
        UNIQUE (address, port)
      )
    """)

    _create_lock_statement = dedent("""\
      LOCK TABLE eventloops IN EXCLUSIVE MODE
    """)

    _create_index_check_statement = dedent("""\
      SELECT 1 FROM pg_catalog.pg_indexes
       WHERE schemaname = CURRENT_SCHEMA()
         AND tablename = 'eventloops'
         AND indexname = 'eventloops_name_idx'
    """)

    _create_index_statement = dedent("""\
      CREATE INDEX eventloops_name_idx ON eventloops (name)
    """)

    def _do_create(self, cursor):
        cursor.execute(self._create_statement)
        # Lock the table exclusine to prevent a race when checking for
        # the presence of the eventloops_name_idx index.
        cursor.execute(self._create_lock_statement)
        cursor.execute(self._create_index_check_statement)
        if list(cursor) == []:
            cursor.execute(self._create_index_statement)

    _delete_statement = "DELETE FROM eventloops WHERE name = %s"

    def _do_delete(self, cursor):
        cursor.execute(self._delete_statement, [eventloop.loop.name])

    _insert_statement = "INSERT INTO eventloops (name, address, port) VALUES "
    _insert_values_statement = "(%s, %s, %s)"

    def _do_insert(self, cursor):
        name = eventloop.loop.name
        statement, values = [], []
        for addr, port in self._get_addresses():
            statement.append(self._insert_values_statement)
            values.extend([name, addr, port])
        if len(statement) != 0:
            statement = self._insert_statement + ", ".join(statement)
            cursor.execute(statement, values)

    _collect_statement = dedent("""\
      DELETE FROM eventloops WHERE
        updated < (NOW() - INTERVAL '5 minutes')
    """)

    def _do_collect(self, cursor):
        cursor.execute(self._collect_statement)

    _select_statement = "SELECT name, address, port FROM eventloops"

    def _do_select(self, cursor):
        cursor.execute(self._select_statement)
