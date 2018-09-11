# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# TODO: Description here.
"""..."""

__all__ = []

import random
from textwrap import dedent
from unittest.mock import sentinel

from django.core.handlers.wsgi import WSGIHandler
from lxml import html
from maasserver import (
    eventloop,
    webapp,
)
from maasserver.testing.listener import FakePostgresListenerService
from maasserver.webapp import OverlaySite
from maasserver.websockets.protocol import WebSocketFactory
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from provisioningserver.utils.twisted import reducedWebLogFormatter
from testtools.matchers import (
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
    Not,
)
from twisted.internet import reactor
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.web.error import UnsupportedMethod
from twisted.web.resource import (
    NoResource,
    Resource,
)
from twisted.web.server import Site
from twisted.web.test.requesthelper import (
    DummyChannel,
    DummyRequest,
)


class TestCleanPathRequest(MAASTestCase):

    def test_requestReceived_converts_extra_slashes_to_single(self):
        mock_super_requestReceived = self.patch(
            webapp.Request, "requestReceived")
        request = webapp.CleanPathRequest(DummyChannel(), sentinel.queued)
        path_pieces = [
            factory.make_name("path").encode("utf-8")
            for _ in range(3)
            ]
        double_path = (b"/" * random.randint(2, 8)).join(path_pieces)
        single_path = b"/".join(path_pieces)
        request.requestReceived(
            sentinel.command, double_path, sentinel.version)
        self.assertThat(
            mock_super_requestReceived,
            MockCalledOnceWith(
                sentinel.command, single_path, sentinel.version))

    def test_requestReceived_converts_extra_slashes_ignores_args(self):
        mock_super_requestReceived = self.patch(
            webapp.Request, "requestReceived")
        request = webapp.CleanPathRequest(DummyChannel(), sentinel.queued)
        path_pieces = [
            factory.make_name("path").encode("utf-8")
            for _ in range(3)
            ]
        args = b"?op=extra//data"
        double_path = (b"/" * random.randint(2, 8)).join(path_pieces) + args
        single_path = b"/".join(path_pieces) + args
        request.requestReceived(
            sentinel.command, double_path, sentinel.version)
        self.assertThat(
            mock_super_requestReceived,
            MockCalledOnceWith(
                sentinel.command, single_path, sentinel.version))


class TestOverlaySite(MAASTestCase):

    def test__init__(self):
        root = Resource()
        site = OverlaySite(root)
        self.assertThat(site, IsInstance(Site))

    def test_getResourceFor_returns_no_resource_wo_underlay(self):
        root = Resource()
        site = OverlaySite(root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        self.assertThat(resource, IsInstance(NoResource))

    def test_getResourceFor_wraps_render_wo_underlay(self):
        root = Resource()
        maas = Resource()
        mock_render = self.patch(maas, 'render')
        root.putChild(b'MAAS', maas)
        site = OverlaySite(root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        self.assertThat(resource, Is(maas))
        self.assertThat(resource.render, Not(Is(mock_render)))
        resource.render(request)
        self.assertThat(mock_render, MockCalledOnceWith(request))

    def test_getResourceFor_wraps_render_wo_underlay_raises_no_method(self):
        root = Resource()
        maas = Resource()
        root.putChild(b'MAAS', maas)
        site = OverlaySite(root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        self.assertThat(resource, Is(maas))
        self.assertRaises(UnsupportedMethod, resource.render, request)

    def test_getResourceFor_returns_resource_from_underlay(self):
        underlay_root = Resource()
        underlay_maas = Resource()
        underlay_root.putChild(b'MAAS', underlay_maas)
        overlay_root = Resource()
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        self.assertThat(resource, Is(underlay_maas))

    def test_getResourceFor_calls_render_on_underlay_when_no_method(self):
        underlay_root = Resource()
        underlay_maas = Resource()
        mock_underlay_maas_render = self.patch(underlay_maas, 'render')
        underlay_root.putChild(b'MAAS', underlay_maas)
        overlay_root = Resource()
        overlay_maas = Resource()
        overlay_root.putChild(b'MAAS', overlay_maas)
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        resource.render(request)
        self.assertThat(mock_underlay_maas_render, MockCalledOnceWith(request))

    def test_getResourceFor_doesnt_wrapper_render_if_already_wrapped(self):
        underlay_root = Resource()
        overlay_root = Resource()
        overlay_maas = Resource()
        mock_render = self.patch(overlay_maas, 'render')
        mock_render.__overlay_wrapped__ = True
        overlay_root.putChild(b'MAAS', overlay_maas)
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        self.assertIs(mock_render, resource.render)

    def test_getResourceFor_does_wrapper_render_not_wrapped(self):
        underlay_root = Resource()
        overlay_root = Resource()
        overlay_maas = Resource()
        original_render = overlay_maas.render
        overlay_root.putChild(b'MAAS', overlay_maas)
        site = OverlaySite(overlay_root)
        site.underlay = Site(underlay_root)
        request = DummyRequest([b'MAAS'])
        resource = site.getResourceFor(request)
        self.assertIsNot(original_render, resource.render)


class TestResourceOverlay(MAASTestCase):

    def make_resourceoverlay(self):
        return webapp.ResourceOverlay(Resource())

    def test__init__(self):
        resource = self.make_resourceoverlay()
        self.assertThat(resource, IsInstance(Resource))

    def test_getChild(self):
        resource = self.make_resourceoverlay()
        self.assertThat(resource, IsInstance(webapp.ResourceOverlay))
        self.assertThat(resource.basis, IsInstance(Resource))


class TestWebApplicationService(MAASTestCase):

    def make_endpoint(self):
        return TCP4ServerEndpoint(reactor, 0, interface="localhost")

    def make_webapp(self):
        listener = FakePostgresListenerService()
        service_endpoint = self.make_endpoint()
        service = webapp.WebApplicationService(
            service_endpoint, listener, sentinel.status_worker)
        # Patch the getServiceNamed so the WebSocketFactory does not
        # error trying to register for events from the RPC service. In this
        # test the RPC service is not started.
        self.patch(eventloop.services, "getServiceNamed")
        return service

    def test__init_creates_site(self):
        service = self.make_webapp()
        self.assertThat(service.site, IsInstance(Site))
        self.assertThat(service.site, MatchesStructure(
            requestFactory=Is(webapp.CleanPathRequest),
            _logFormatter=Is(reducedWebLogFormatter),
            timeOut=Is(None),
        ))
        self.assertThat(service.websocket, IsInstance(WebSocketFactory))

    def test__default_site_renders_starting_page(self):
        service = self.make_webapp()
        request = DummyRequest("any/where".split("/"))
        resource = service.site.getResourceFor(request)
        content = resource.render(request)
        page = html.fromstring(content)
        self.expectThat(
            page.find(".//title").text_content(),
            Equals("503 - MAAS is starting"))
        self.expectThat(
            page.find(".//h1").text_content(),
            Equals("MAAS is starting"))
        self.expectThat(
            page.find(".//p").text_content(),
            Equals("Please try again in a few seconds."))
        self.assertEqual(
            ['5'],
            request.responseHeaders.getRawHeaders("retry-after"))

    def test__startService_starts_application(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        service.startService()

        self.assertTrue(service.running)

    def test__error_when_starting_is_logged(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        mock_prepare = self.patch_autospec(service, "prepareApplication")
        mock_prepare.side_effect = factory.make_exception()

        # The failure is logged.
        with TwistedLoggerFixture() as logger:
            service.startService()

        self.assertDocTestMatches(
            dedent("""\
            MAAS web application failed to start
            Traceback (most recent call last):
            ...
            maastesting.factory.TestException#...
            """),
            logger.output)

    def test__error_when_starting_changes_page_to_error(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        mock_prepare = self.patch_autospec(service, "prepareApplication")
        mock_prepare.side_effect = factory.make_exception()

        # No error is returned.
        with TwistedLoggerFixture():
            service.startService()

        # The site's page (for any path) shows the error.
        request = DummyRequest("any/where".split("/"))
        resource = service.site.getResourceFor(request)
        content = resource.render(request)
        page = html.fromstring(content)
        self.expectThat(
            page.find(".//title").text_content(),
            Equals("503 - MAAS failed to start"))
        self.expectThat(
            page.find(".//h1").text_content(),
            Equals("MAAS failed to start"))
        self.assertDocTestMatches(
            dedent("""\
            Traceback (most recent call last):
            ...
            maastesting.factory.TestException#...
            """),
            page.find(".//pre").text_content())

    def test__successful_start_installs_wsgi_resource(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

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
            b"MAAS", request=None)
        self.assertThat(
            underlay_maas_resource, IsInstance(webapp.ResourceOverlay))
        self.assertThat(underlay_maas_resource.basis, MatchesStructure(
            _reactor=Is(reactor), _threadpool=Is(service.threadpool),
            _application=IsInstance(WSGIHandler)))

    def test__stopService_stops_the_service(self):
        service = self.make_webapp()
        service.startService()
        self.assertTrue(service.running)
        service.stopService()
        self.assertFalse(service.running)
