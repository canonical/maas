# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


import random
from unittest.mock import sentinel

from django.core.handlers.wsgi import WSGIHandler
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.web.error import UnsupportedMethod
from twisted.web.resource import NoResource, Resource
from twisted.web.server import Site
from twisted.web.test.requesthelper import DummyChannel, DummyRequest

from maasserver import eventloop, webapp
from maasserver.testing.listener import FakePostgresListenerService
from maasserver.webapp import OverlaySite
from maasserver.websockets.protocol import WebSocketFactory
from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
from provisioningserver.utils.twisted import reducedWebLogFormatter


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
        mock_super_requestReceived.assert_called_once_with(
            sentinel.command, single_path, sentinel.version
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
        mock_super_requestReceived.assert_called_once_with(
            sentinel.command, single_path, sentinel.version
        )


class TestOverlaySite(MAASTestCase):
    def test_init__(self):
        root = Resource()
        site = OverlaySite(root)
        self.assertIsInstance(site, Site)

    def test_getResourceFor_returns_no_resource_wo_underlay(self):
        root = Resource()
        site = OverlaySite(root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertIsInstance(resource, NoResource)

    def test_getResourceFor_wraps_render_wo_underlay(self):
        root = Resource()
        maas = Resource()
        mock_render = self.patch(maas, "render")
        root.putChild(b"MAAS", maas)
        site = OverlaySite(root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertIs(resource, maas)
        self.assertIsNot(resource.render, mock_render)
        resource.render(request)
        mock_render.assert_called_once_with(request)

    def test_getResourceFor_wraps_render_wo_underlay_raises_no_method(self):
        root = Resource()
        maas = Resource()
        root.putChild(b"MAAS", maas)
        site = OverlaySite(root)
        request = DummyRequest([b"MAAS"])
        resource = site.getResourceFor(request)
        self.assertIs(resource, maas)
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
        self.assertIs(resource, underlay_maas)

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
        mock_underlay_maas_render.assert_called_once_with(request)

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
        self.assertIsInstance(resource, Resource)

    def test_getChild(self):
        resource = self.make_resourceoverlay()
        self.assertIsInstance(resource, webapp.ResourceOverlay)
        self.assertIsInstance(resource.basis, Resource)


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
        self.assertIsInstance(service.site, Site)
        self.assertIs(service.site.requestFactory, webapp.CleanPathRequest)
        self.assertIs(service.site._logFormatter, reducedWebLogFormatter)
        self.assertIsNone(service.site.timeOut)
        self.assertIsInstance(service.websocket, WebSocketFactory)

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
        self.assertIsInstance(site, OverlaySite)
        resource = service.site.resource
        self.assertIsInstance(resource, Resource)
        overlay_resource = resource.getChildWithDefault(b"MAAS", request=None)
        self.assertIsInstance(overlay_resource, Resource)

        # Underlay
        site = service.site.underlay
        self.assertIsInstance(site, Site)
        underlay_resource = site.resource
        self.assertIsInstance(underlay_resource, Resource)
        underlay_maas_resource = underlay_resource.getChildWithDefault(
            b"MAAS", request=None
        )
        self.assertIsInstance(underlay_maas_resource, webapp.ResourceOverlay)
        self.assertIs(underlay_maas_resource.basis._reactor, reactor)
        self.assertIs(
            underlay_maas_resource.basis._threadpool, service.threadpool
        )
        self.assertIsInstance(
            underlay_maas_resource.basis._application, WSGIHandler
        )
