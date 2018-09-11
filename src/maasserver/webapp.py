# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Web Application."""

__all__ = [
    "WebApplicationService",
]

import copy
from functools import partial
from http.client import SERVICE_UNAVAILABLE
import re

from django.conf import settings
from lxml import html
from maasserver import concurrency
from maasserver.utils.threads import deferToDatabase
from maasserver.utils.views import WebApplicationHandler
from maasserver.websockets.protocol import WebSocketFactory
from maasserver.websockets.websockets import (
    lookupProtocolForFactory,
    WebSocketsResource,
)
from metadataserver.api_twisted import StatusHandlerResource
from provisioningserver.logger import LegacyLogger
from provisioningserver.utils.twisted import (
    asynchronous,
    reducedWebLogFormatter,
    ThreadPoolLimiter,
)
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.python import failure
from twisted.web.error import UnsupportedMethod
from twisted.web.resource import (
    ErrorPage,
    NoResource,
    Resource,
)
from twisted.web.server import (
    Request,
    Site,
)
from twisted.web.static import File
from twisted.web.util import Redirect
from twisted.web.wsgi import WSGIResource


log = LegacyLogger()


class StartPage(ErrorPage, object):
    def __init__(self):
        super(StartPage, self).__init__(
            status=int(SERVICE_UNAVAILABLE), brief="MAAS is starting",
            detail="Please try again in a few seconds.")

    def render(self, request):
        request.setHeader(b"Retry-After", b"5")
        return super(StartPage, self).render(request)


class StartFailedPage(ErrorPage, object):

    def __init__(self, failure):
        traceback = html.Element("pre")
        traceback.text = failure.getTraceback()
        super(StartFailedPage, self).__init__(
            status=int(SERVICE_UNAVAILABLE), brief="MAAS failed to start",
            detail=html.tostring(traceback, encoding=str))


class CleanPathRequest(Request, object):
    """A request that supports '/+' in the path.

    It converts all '/+' in the path to a single '/'.
    """

    def requestReceived(self, command, path, version):
        path, sep, args = path.partition(b"?")
        path = re.sub(rb'/+', b'/', path)
        path = b"".join([path, sep, args])
        return super(CleanPathRequest, self).requestReceived(
            command, path, version)


class OverlaySite(Site):
    """A site that is over another site.

    If this site cannot resolve a valid resource to handle the request, then
    the underlay site gets passed the request to process.
    """

    underlay = None

    def getResourceFor(self, request):
        """Override to support an underlay site.

        If this site cannot return a valid resource to request is passed to
        the underlay site to resolve the request.
        """
        def call_underlay(request):
            # Reset the paths and forward to the underlay site.
            request.prepath = []
            request.postpath = postpath
            return self.underlay.getResourceFor(request)

        def wrap_render(orig_render, request):
            # Wrap the render call of the resource, catching any
            # UnsupportedMethod exceptions and forwarding those onto
            # the underlay site.
            try:
                return orig_render(request)
            except UnsupportedMethod:
                if self.underlay is not None:
                    resource = call_underlay(request)
                    return resource.render(request)
                else:
                    raise

        postpath = copy.copy(request.postpath)
        result = super(OverlaySite, self).getResourceFor(request)
        if isinstance(result, NoResource) and self.underlay is not None:
            return call_underlay(request)
        else:
            if hasattr(result.render, '__overlay_wrapped__'):
                # Render method for the resulting resource has already been
                # wrapped, so don't wrap it again.
                return result
            else:
                # First time this resource has been returned. Wrap the render
                # method so if the resource doesn't support that method
                # it will be passed to the underlay.
                result.render = partial(wrap_render, result.render)
                result.render.__overlay_wrapped__ = True
            return result


class ResourceOverlay(Resource, object):
    """A resource that can fall-back to a basis resource.

    Children can be set using `putChild()` as usual. However, if path
    traversal doesn't find one of these children, the `basis` resource is
    returned, and path traversal will then be tried again through that it. In
    addition, if path traversal results in this resource, rendering will also
    be passed-through to the `basis` resource.

    :ivar basis: An `IResource`.
    """

    def __init__(self, basis):
        super(ResourceOverlay, self).__init__()
        self.basis = basis

    def getChild(self, path, request):
        """Return the basis resource.

        Also undo the path traversal that brought us here so that the basis
        resource can be asked for it.
        """
        # Move back up one level in path traversal.
        request.postpath.insert(0, path)
        request.prepath.pop()
        # Traversal will continue with the basis resource.
        return self.basis

    def render(self, request):
        """Pass-through to the basis resource."""
        return self.basis.render(request)


class WebApplicationService(StreamServerEndpointService):
    """Service encapsulating the Django web application.

    This shows a default "MAAS is starting" web page until Django is up. If
    Django cannot be started, the page is replaced by the error that caused
    start-up to fail.

    :ivar site: The site object that wraps a WSGI resource.
    :ivar threadpool: The thread-pool used for servicing requests to
        the web application.
    """

    def __init__(self, endpoint, listener, status_worker):
        self.site = OverlaySite(
            StartPage(), logFormatter=reducedWebLogFormatter, timeout=None)
        self.site.requestFactory = CleanPathRequest
        super(WebApplicationService, self).__init__(endpoint, self.site)
        self.websocket = WebSocketFactory(listener)
        self.threadpool = ThreadPoolLimiter(
            reactor.threadpoolForDatabase, concurrency.webapp)
        self.status_worker = status_worker

    def prepareApplication(self):
        """Return the WSGI application.

        If we run servers on multiple endpoints this ought to be extracted
        into a separate function, so that each server uses the same
        application.
        """
        return WebApplicationHandler()

    def startWebsocket(self):
        """Start the websocket factory for the `WebSocketsResource`."""
        self.websocket.startFactory()

    def installApplication(self, application):
        """Install the WSGI application into the Twisted site.

        It's installed as a child with path "MAAS". This matches the default
        front-end configuration (i.e. Apache) so that there's no need to force
        script names.
        """
        # Setup resources to process paths that twisted handles.
        metadata = Resource()
        metadata.putChild(b'status', StatusHandlerResource(self.status_worker))

        maas = Resource()
        maas.putChild(b'metadata', metadata)
        maas.putChild(b'static', File(settings.STATIC_ROOT))
        maas.putChild(
            b'ws',
            WebSocketsResource(lookupProtocolForFactory(self.websocket)))

        root = Resource()
        root.putChild(b'', Redirect(b"MAAS/"))
        root.putChild(b'MAAS', maas)

        # Setup the resources to process paths that django handles.
        underlay_maas = ResourceOverlay(
            WSGIResource(reactor, self.threadpool, application))
        underlay_root = Resource()
        underlay_root.putChild(b'MAAS', underlay_maas)
        underlay_site = Site(
            underlay_root, logFormatter=reducedWebLogFormatter)
        underlay_site.requestFactory = CleanPathRequest

        # Setup the main resource as the twisted handler and the underlay
        # resource as the django handler.
        self.site.resource = root
        self.site.underlay = underlay_site

    def installFailed(self, failure):
        """Display a page explaining why the web app could not start."""
        self.site.resource = StartFailedPage(failure)
        log.err(failure, "MAAS web application failed to start")

    @inlineCallbacks
    def startApplication(self):
        """Start the Django application, and install it."""
        try:
            application = yield deferToDatabase(self.prepareApplication)
            self.startWebsocket()
            self.installApplication(application)
        except:
            self.installFailed(failure.Failure())

    @asynchronous(timeout=30)
    def startService(self):
        super(WebApplicationService, self).startService()
        return self.startApplication()

    @asynchronous(timeout=30)
    def stopService(self):
        d = super(WebApplicationService, self).stopService()
        d.addCallback(lambda _: self.websocket.stopFactory())
        return d
