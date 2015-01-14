# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Web Application."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "WebApplicationService",
]

from httplib import SERVICE_UNAVAILABLE

from lxml import html
from provisioningserver.utils.twisted import asynchronous
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import reactor
from twisted.internet.threads import deferToThread
from twisted.python import log
from twisted.python.threadpool import ThreadPool
from twisted.web.resource import (
    ErrorPage,
    Resource,
    )
from twisted.web.server import Site
from twisted.web.wsgi import WSGIResource


class StartPage(ErrorPage, object):

    def __init__(self):
        super(StartPage, self).__init__(
            status=SERVICE_UNAVAILABLE, brief="MAAS is starting",
            detail="Please try again in a few seconds.")

    def render(self, request):
        request.setHeader(b"Retry-After", b"5")
        return super(StartPage, self).render(request)


class StartFailedPage(ErrorPage, object):

    def __init__(self, failure):
        traceback = html.Element("pre")
        traceback.text = failure.getTraceback()
        super(StartFailedPage, self).__init__(
            status=SERVICE_UNAVAILABLE, brief="MAAS failed to start",
            detail=html.tostring(traceback, encoding=unicode))


class WebApplicationService(StreamServerEndpointService):
    """Service encapsulating the Django web application.

    This shows a default "MAAS is starting" web page until Django is up. If
    Django cannot be started, the page is replaced by the error that caused
    start-up to fail.

    :ivar site: The site object that wraps a WSGI resource.
    :ivar threadpool: The thread-pool used for servicing requests to
        the web application.
    """

    def __init__(self, endpoint):
        self.site = Site(StartPage())
        super(WebApplicationService, self).__init__(endpoint, self.site)
        self.threadpool = ThreadPool(name=self.__class__.__name__)

    def prepareApplication(self):
        """Perform start-up tasks and return the WSGI application.

        If we run servers on multiple endpoints this ought to be extracted
        into a separate function, so that each server uses the same
        application.
        """
        from maasserver import start_up
        start_up.start_up()
        from maasserver.utils.views import WebApplicationHandler
        return WebApplicationHandler()

    def installApplication(self, application):
        """Install the WSGI application into the Twisted site.

        It's installed as a child with path "MAAS". This matches the default
        front-end configuration (i.e. Apache) so that there's no need to force
        script names.
        """
        root = Resource()
        root.putChild("MAAS", WSGIResource(
            reactor, self.threadpool, application))
        self.site.resource = root

    def installFailed(self, failure):
        """Display a page explaining why the web app could not start."""
        self.site.resource = StartFailedPage(failure)
        log.err(failure, "MAAS web application failed to start")

    def startApplication(self):
        """Start the Django application, and install it."""
        d = deferToThread(self.prepareApplication)
        d.addCallback(self.installApplication)
        d.addErrback(self.installFailed)
        return d

    @asynchronous(timeout=30)
    def startService(self):
        self.threadpool.start()
        super(WebApplicationService, self).startService()
        return self.startApplication()

    @asynchronous(timeout=30)
    def stopService(self):
        d = super(WebApplicationService, self).stopService()
        # Stop the threadpool from a thread in the reactor's thread-pool so
        # that we don't block the reactor thread (or the thread-pool we're
        # trying to stop).
        d.addCallback(lambda _: deferToThread(self.threadpool.stop))
        return d
