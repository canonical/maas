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
]

from provisioningserver.rpc import region
from twisted.application import service
from twisted.internet import defer
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.internet.protocol import Factory
from twisted.protocols import amp
from twisted.python import log


class Region(amp.AMP):
    """The RPC protocol supported by a region controller.

    This can be used on the client or server end of a connection; once a
    connection is established, AMP is symmetric.
    """

    @region.ReportBootImages.responder
    def report_boot_images(self, uuid, images):
        print(uuid, images)
        return {}


class RegionService(service.Service, object):
    """A region controller RPC service.

    This is a service - in the Twisted sense - that exposes the
    ``Region`` protocol on a port.

    :ivar starting: Either `None`, or a :class:`Deferred` that fires
        with the port that's been opened, or the error that prevented it
        from opening.
    """

    starting = None

    def __init__(self, reactor):
        super(RegionService, self).__init__()
        self.endpoint = TCP4ServerEndpoint(reactor, 0)
        self.factory = Factory.forProtocol(Region)
        self._port = None

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

    def stopService(self):
        """Stop listening."""
        self.starting.cancel()

        if self._port is None:
            d = defer.succeed(None)
        else:
            d = self._port.stopListening()

        def stop_service(ignore):
            return super(RegionService, self).stopService()
        d.addCallback(stop_service)

        return d

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
