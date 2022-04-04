# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pathlib import Path
import random
from unittest.mock import sentinel

from django.core.handlers.wsgi import WSGIHandler
from testtools.matchers import Is, IsInstance, MatchesStructure, Not
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.web.error import UnsupportedMethod
from twisted.web.resource import NoResource, Resource
from twisted.web.server import Site
from twisted.web.test.requesthelper import DummyChannel, DummyRequest

from maasserver import eventloop, webapp
from maasserver.testing.listener import FakePostgresListenerService
from maasserver.webapp import DocsFallbackFile, OverlaySite
from maasserver.websockets.protocol import WebSocketFactory
from maastesting.factory import factory
from maastesting.fixtures import TempDirectory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.twisted import reducedWebLogFormatter


class TestDocsFallbackFile(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.base_dir = self.useFixture(TempDirectory())
        self.docs = DocsFallbackFile(self.base_dir.path)

    def touch_file(self, path):
        Path(self.base_dir.join(path)).touch()

    def test_html_404(self):
        request = DummyRequest([b"foo.html"])
        resource = self.docs.getChild(b"foo.html", request)
        self.assertTrue(resource.path.endswith("404.html"), resource.path)

    def test_other_404(self):
        request = DummyRequest([b"foo.jpg"])
        resource = self.docs.getChild(b"foo.jpg", request)
        self.assertTrue(resource.path.endswith("404.html"), resource.path)

    def test_html_resource(self):
        self.touch_file("foo.html")
        request = DummyRequest([b"foo.html"])
        resource = self.docs.getChild(b"foo.html", request)
        self.assertTrue(resource.path.endswith("foo.html"), resource.path)

    def test_other_resource(self):
        self.touch_file("foo.jpg")
        request = DummyRequest([b"foo.jpg"])
        resource = self.docs.getChild(b"foo.jpg", request)
        self.assertTrue(resource.path.endswith("foo.jpg"), resource.path)

    def test_append_html(self):
        self.touch_file("foo.html")
        request = DummyRequest([b"foo"])
        resource = self.docs.getChild(b"foo", request)
        self.assertTrue(resource.path.endswith("foo.html"), resource.path)

    def test_index(self):
        self.touch_file("maas-documentation-25.html")
        request = DummyRequest([b""])
        resource = self.docs.getChild(b"", request)
        self.assertTrue(
            resource.path.endswith("maas-documentation-25.html"), resource.path
        )


class TestCleanPathRequest(MAASTestCase):
    def test_requestReceived_converts_extra_slashes_to_single(self):
        mock_super_requestReceived = self.patch(
            webapp.Request, "requestReceived"
        )
        request = webapp.CleanPathRequest(DummyChannel(), sentinel.queued)
        path_pieces = [
            factory.make_name("path").encode("utf-8") for _ in range(3)
        ]
        double_path = (b"/" * random.randint(2, 8)).join(path_pieces)
        single_path = b"/".join(path_pieces)
        request.requestReceived(
            sentinel.command, double_path, sentinel.version
        )
        self.assertThat(
            mock_super_requestReceived,
            MockCalledOnceWith(
                sentinel.command, single_path, sentinel.version
            ),
        )

    def test_requestReceived_converts_extra_slashes_ignores_args(self):
        mock_super_requestReceived = self.patch(
            webapp.Request, "requestReceived"
        )
        request = webapp.CleanPathRequest(DummyChannel(), sentinel.queued)
        path_pieces = [
            factory.make_name("path").encode("utf-8") for _ in range(3)
        ]
        args = b"?op=extra//data"
        double_path = (b"/" * random.randint(2, 8)).join(path_pieces) + args
        single_path = b"/".join(path_pieces) + args
        request.requestReceived(
            sentinel.command, double_path, sentinel.version
        )
        self.assertThat(
            mock_super_requestReceived,
            MockCalledOnceWith(
                sentinel.command, single_path, sentinel.version
            ),
        )


class TestOverlaySite(MAASTestCase):
    def test_init__(self):
        root = Resource()
        site = OverlaySite(root)
        self.assertThat(site, IsInstance(Site))

    def test_getResourceFor_returns_no_resource_wo_underlay(self):
        root = Resource()
        site = OverlaySite(root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertThat(resource, IsInstance(NoResource))

    def test_getResourceFor_wraps_render_wo_underlay(self):
        root = Resource()
        maas = Resource()
        mock_render = self.patch(maas, "render")
        root.putChild(b"MAAS", maas)
        site = OverlaySite(root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertThat(resource, Is(maas))
        self.assertThat(resource.render, Not(Is(mock_render)))
        resource.render(request)
        self.assertThat(mock_render, MockCalledOnceWith(request))

    def test_getResourceFor_wraps_render_wo_underlay_raises_no_method(self):
        root = Resource()
        maas = Resource()
        root.putChild(b"MAAS", maas)
        site = OverlaySite(root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertThat(resource, Is(maas))
        self.assertRaises(UnsupportedMethod, resource.render, request)

    def test_getResourceFor_returns_resource_from_underlay(self):
        underlay_root = Resource()
        underlay_maas = Resource()
        underlay_root.putChild(b"MAAS", underlay_maas)
        overlay_root = Resource()
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertThat(resource, Is(underlay_maas))

    def test_getResourceFor_calls_render_on_underlay_when_no_method(self):
        underlay_root = Resource()
        underlay_maas = Resource()
        mock_underlay_maas_render = self.patch(underlay_maas, "render")
        underlay_root.putChild(b"MAAS", underlay_maas)
        overlay_root = Resource()
        overlay_maas = Resource()
        overlay_root.putChild(b"MAAS", overlay_maas)
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        resource.render(request)
        self.assertThat(mock_underlay_maas_render, MockCalledOnceWith(request))

    def test_getResourceFor_doesnt_wrapper_render_if_already_wrapped(self):
        underlay_root = Resource()
        overlay_root = Resource()
        overlay_maas = Resource()
        mock_render = self.patch(overlay_maas, "render")
        mock_render.__overlay_wrapped__ = True
        overlay_root.putChild(b"MAAS", overlay_maas)
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertIs(mock_render, resource.render)

    def test_getResourceFor_does_wrapper_render_not_wrapped(self):
        underlay_root = Resource()
        overlay_root = Resource()
        overlay_maas = Resource()
        original_render = overlay_maas.render
        overlay_root.putChild(b"MAAS", overlay_maas)
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertIsNot(original_render, resource.render)


class TestResourceOverlay(MAASTestCase):
    def make_resourceoverlay(self):
        return webapp.ResourceOverlay(Resource())

    def test_init__(self):
        resource = self.make_resourceoverlay()
        self.assertThat(resource, IsInstance(Resource))

    def test_getChild(self):
        resource = self.make_resourceoverlay()
        self.assertThat(resource, IsInstance(webapp.ResourceOverlay))
        self.assertThat(resource.basis, IsInstance(Resource))


class TestWebApplicationService(MAASTestCase):
    def setUp(self):
        super().setUp()
        # Patch the getServiceNamed so the WebSocketFactory does not
        # error trying to register for events from the RPC service. In this
        # test the RPC service is not started.
        self.patch(eventloop.services, "getServiceNamed")

    def make_webapp(self):
        listener = FakePostgresListenerService()
        service = webapp.WebApplicationService(
            listener, sentinel.status_worker
        )
        mock_makeEndpoint = self.patch(service, "_makeEndpoint")
        mock_makeEndpoint.return_value = TCP4ServerEndpoint(
            reactor, 0, interface="localhost"
        )
        return service

    def test_init_creates_site(self):
        service = self.make_webapp()
        self.assertThat(service.site, IsInstance(Site))
        self.assertThat(
            service.site,
            MatchesStructure(
                requestFactory=Is(webapp.CleanPathRequest),
                _logFormatter=Is(reducedWebLogFormatter),
                timeOut=Is(None),
            ),
        )
        self.assertThat(service.websocket, IsInstance(WebSocketFactory))

    def test_start_and_stop_the_service(self):
        service = self.make_webapp()
        # Both privileged and and normal start must be called, as twisted
        # multi-service will do the same.
        service.privilegedStartService()
        self.assertTrue(service.starting)
        service.startService()
        self.assertTrue(service.running)
        service.stopService()
        self.assertFalse(service.running)
        self.assertFalse(service.starting)

    def test_successful_start_installs_wsgi_resource(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        # Both privileged and and normal start must be called, as twisted
        # multi-service will do the same.
        service.privilegedStartService()
        service.startService()

        # Overlay
        site = service.site
        self.assertThat(site, IsInstance(OverlaySite))
        resource = service.site.resource
        self.assertThat(resource, IsInstance(Resource))
        overlay_resource = resource.getChildWithDefault(b"MAAS", request=None)
        self.assertThat(overlay_resource, IsInstance(Resource))

        # Underlay
        site = service.site.underlay
        self.assertThat(site, IsInstance(Site))
        underlay_resource = site.resource
        self.assertThat(underlay_resource, IsInstance(Resource))
        underlay_maas_resource = underlay_resource.getChildWithDefault(
            b"MAAS", request=None
        )
        self.assertThat(
            underlay_maas_resource, IsInstance(webapp.ResourceOverlay)
        )
        self.assertThat(
            underlay_maas_resource.basis,
            MatchesStructure(
                _reactor=Is(reactor),
                _threadpool=Is(service.threadpool),
                _application=IsInstance(WSGIHandler),
            ),
        )
