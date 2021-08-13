# Copyright 2014-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""The MAAS Web Application."""


import copy
from functools import partial
import os
import re
import socket

from django.conf import settings
from twisted.application.internet import StreamServerEndpointService
from twisted.internet import reactor
from twisted.internet.defer import inlineCallbacks
from twisted.internet.endpoints import AdoptedStreamServerEndpoint
from twisted.web.error import UnsupportedMethod
from twisted.web.resource import NoResource, Resource
from twisted.web.server import Request, Site
from twisted.web.static import File
from twisted.web.util import Redirect
from twisted.web.wsgi import WSGIResource

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
from provisioningserver.utils.fs import get_root_path
from provisioningserver.utils.twisted import (
    asynchronous,
    reducedWebLogFormatter,
    ThreadPoolLimiter,
)

log = LegacyLogger()


class CleanPathRequest(Request):
    """A request that supports '/+' in the path.

    It converts all '/+' in the path to a single '/'.
    """

    def requestReceived(self, command, path, version):
        path, sep, args = path.partition(b"?")
        path = re.sub(rb"/+", b"/", path)
        path = b"".join([path, sep, args])
        return super().requestReceived(command, path, version)


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
        result = super().getResourceFor(request)
        if isinstance(result, NoResource) and self.underlay is not None:
            return call_underlay(request)
        else:
            if hasattr(result.render, "__overlay_wrapped__"):
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


class ResourceOverlay(Resource):
    """A resource that can fall-back to a basis resource.

    Children can be set using `putChild()` as usual. However, if path
    traversal doesn't find one of these children, the `basis` resource is
    returned, and path traversal will then be tried again through that it. In
    addition, if path traversal results in this resource, rendering will also
    be passed-through to the `basis` resource.

    :ivar basis: An `IResource`.
    """

    def __init__(self, basis):
        super().__init__()
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


class DefaultFile(File):
    """
    A `File` resource that always returns the same file no matter the
    path.
    """

    def getChild(self, path, request):
        return self


class NoListingFile(File):
    """
    A `File` resource that returns childNotFound instead of listing the directory contents.
    """

    def directoryListing(self):
        return self.childNotFound


class DefaultFallbackFile(NoListingFile):
    """
    A `NoListingFile` that returns the fallback file when a path is not found.
    """

    def __init__(self, *args, **kwargs):
        fallback = kwargs.pop("fallback", "index.html")
        super().__init__(*args, **kwargs)
        self.childNotFound = DefaultFile(self.child(fallback).path)


class DocsFallbackFile(NoListingFile):
    """
    A `NoListingFile` that returns the fallback file when a path is not found.
    """

    def __init__(self, *args, **kwargs):
        fallback = kwargs.pop("fallback", "404.html")
        super().__init__(*args, **kwargs)
        self.childNotFound = DefaultFile(self.child(fallback).path)

    def getChild(self, path, request):
        if path == b"":
            return self.getChild("maas-documentation-25.html", request)
        child = super().getChild(path, request)
        if child is self.childNotFound and not path.endswith(b".html"):
            child = super().getChild(path + b".html", request)
        return child


class WebApplicationService(StreamServerEndpointService):
    """Service encapsulating the Django web application.

    This shows a default "MAAS is starting" web page until Django is up. If
    Django cannot be started, the page is replaced by the error that caused
    start-up to fail.

    :ivar site: The site object that wraps a WSGI resource.
    :ivar threadpool: The thread-pool used for servicing requests to
        the web application.
    """

    def __init__(self, port, listener, status_worker):
        self.port = port
        self.starting = False
        # Start with an empty `Resource`, `installApplication` will configure
        # the root resource. This must be seperated because Django must be
        # start from inside a thread with database access.
        self.site = OverlaySite(
            Resource(), logFormatter=reducedWebLogFormatter, timeout=None
        )
        self.site.requestFactory = CleanPathRequest
        # `endpoint` is set in `privilegedStartService`, at this point the
        # `endpoint` is None.
        super().__init__(None, self.site)
        self.websocket = WebSocketFactory(listener)
        self.threadpool = ThreadPoolLimiter(
            reactor.threadpoolForDatabase, concurrency.webapp
        )
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
        metadata.putChild(b"status", StatusHandlerResource(self.status_worker))

        maas = Resource()
        maas.putChild(b"metadata", metadata)
        maas.putChild(
            b"ws", WebSocketsResource(lookupProtocolForFactory(self.websocket))
        )

        # /MAAS/r/{path} and /MAAS/l/{path} are all resolved by the new MAAS UI
        # react app, and legacy angularjs app respectively.
        # If any paths do not match then its routed to index.html in the new
        # UI code as it uses HTML 5 routing.
        maas.putChild(b"r", DefaultFallbackFile(settings.STATIC_ROOT))

        maas.putChild(b"l", DefaultFallbackFile(settings.STATIC_ROOT))

        # Redirect /MAAS to react app
        maas.putChild(b"", Redirect(b"/MAAS/r/"))

        # Setup static resources
        maas.putChild(
            b"assets",
            NoListingFile(os.path.join(settings.STATIC_ROOT, "assets")),
        )
        maas.putChild(
            b"machine-resources",
            NoListingFile(
                get_root_path() / "usr/share/maas/machine-resources"
            ),
        )

        # Setup static docs
        maas.putChild(
            b"docs",
            DocsFallbackFile(os.path.join(settings.STATIC_ROOT, "docs")),
        )

        root = Resource()
        root.putChild(b"", Redirect(b"MAAS/"))
        root.putChild(b"MAAS", maas)

        # Setup the resources to process paths that django handles.
        underlay_maas = ResourceOverlay(
            WSGIResource(reactor, self.threadpool, application)
        )
        underlay_root = Resource()
        underlay_root.putChild(b"MAAS", underlay_maas)
        underlay_site = Site(
            underlay_root, logFormatter=reducedWebLogFormatter
        )
        underlay_site.requestFactory = CleanPathRequest

        # Setup the main resource as the twisted handler and the underlay
        # resource as the django handler.
        self.site.resource = root
        self.site.underlay = underlay_site

    @inlineCallbacks
    def startApplication(self):
        """Start the Django application, and install it."""
        application = yield deferToDatabase(self.prepareApplication)
        self.startWebsocket()
        self.installApplication(application)

    def _makeEndpoint(self):
        """Make the endpoint for the webapp."""
        # Make a socket with SO_REUSEPORT set so that we can run multiple web
        # applications. This is easier to do from outside of Twisted as there's
        # not yet official support for setting socket options.
        s = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        # N.B, using the IPv6 INADDR_ANY means that getpeername() returns
        # something like: ('::ffff:192.168.133.32', 40588, 0, 0)
        s.bind(("::", self.port))
        # Use a backlog of 50, which seems to be fairly common.
        s.listen(50)

        # Adopt this socket into Twisted's reactor setting the endpoint.
        endpoint = AdoptedStreamServerEndpoint(reactor, s.fileno(), s.family)
        endpoint.port = self.port  # Make it easy to get the port number.
        endpoint.socket = s  # Prevent garbage collection.
        return endpoint

    @asynchronous(timeout=30)
    @inlineCallbacks
    def privilegedStartService(self):
        # Twisted will call `privilegedStartService` followed by `startService`
        # that also calls `privilegedStartService`. Since this method now
        # performs start-up work its possible that it will be called twice.
        # Then endpoint can only be created once or a bad file descriptor
        # error will occur.
        if self.starting:
            return
        self.starting = True

        # Start the application first before starting the service. This ensures
        # that the application is running correctly before any requests
        # can be handled.
        yield self.startApplication()

        # Create the endpoint now that the application is started.
        self.endpoint = self._makeEndpoint()

        # Start the service now that the endpoint has been created.
        super().privilegedStartService()

    @asynchronous(timeout=30)
    def stopService(self):
        def _cleanup(_):
            self.starting = False

        d = super().stopService()
        d.addCallback(lambda _: self.websocket.stopFactory())
        d.addCallback(_cleanup)
        return d
