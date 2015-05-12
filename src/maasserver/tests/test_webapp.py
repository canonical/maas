# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

# TODO: Description here.
"""..."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from textwrap import dedent

import crochet
from django.core.handlers.wsgi import WSGIHandler
from lxml import html
from maasserver import (
    start_up,
    webapp,
)
from maasserver.websockets.protocol import WebSocketFactory
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
from provisioningserver.rpc.testing import TwistedLoggerFixture
from testtools.matchers import (
    ContainsDict,
    Equals,
    Is,
    IsInstance,
    MatchesStructure,
)
from twisted.internet import (
    defer,
    reactor,
)
from twisted.internet.endpoints import TCP4ServerEndpoint
from twisted.python.threadpool import ThreadPool
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.test.requesthelper import DummyRequest


crochet.setup()


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
        service_endpoint = self.make_endpoint()
        service = webapp.WebApplicationService(service_endpoint)
        return service

    def test__init_creates_site_and_threadpool(self):
        service = self.make_webapp()
        self.assertThat(service.site, IsInstance(Site))
        self.assertThat(service.threadpool, IsInstance(ThreadPool))
        self.assertThat(service.websocket, IsInstance(WebSocketFactory))
        # The thread-pool has not been started.
        self.assertFalse(service.threadpool.started)

    def test__default_site_renders_starting_page(self):
        service = self.make_webapp()
        request = DummyRequest(b"any/where".split("/"))
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
        self.expectThat(
            request.outgoingHeaders,
            ContainsDict({"retry-after": Equals("5")}))

    def test__startService_starts_threadpool_websocket_and_application(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        # start_up() isn't safe to call right now, but we only really care
        # that it is called.
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.succeed(None)

        service.startService()

        self.assertTrue(service.running)
        self.assertTrue(service.threadpool.started)
        self.assertThat(start_up.start_up, MockCalledOnceWith())
        self.assertTrue(service.websocket.listener.connected())

    def test__error_when_starting_is_logged(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        start_up_error = factory.make_exception()
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.fail(start_up_error)

        # The failure is logged.
        with TwistedLoggerFixture() as logger:
            service.startService()

        self.assertDocTestMatches(
            dedent("""\
            Site starting on ...
            ---
            MAAS web application failed to start
            Traceback (most recent call last):
            ...
            maastesting.factory.TestException#...
            """),
            logger.output)

    def test__error_when_starting_changes_page_to_error(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        # start_up() isn't safe to call right now, but we only really care
        # that it is called.
        start_up_error = factory.make_exception()
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.fail(start_up_error)

        # No error is returned.
        service.startService()

        # The site's page (for any path) shows the error.
        request = DummyRequest(b"any/where".split("/"))
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
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.succeed(None)

        service.startService()

        resource = service.site.resource
        self.assertThat(resource, IsInstance(Resource))
        overlay_resource = resource.getChildWithDefault("MAAS", request=None)
        self.assertThat(overlay_resource, IsInstance(webapp.ResourceOverlay))
        self.assertThat(overlay_resource.basis, MatchesStructure(
            _reactor=Is(reactor), _threadpool=Is(service.threadpool),
            _application=IsInstance(WSGIHandler)))

    def test__stopService_stops_the_service_threadpool_and_the_websocket(self):
        service = self.make_webapp()
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.succeed(None)

        service.startService()
        service.stopService()

        self.assertFalse(service.running)
        self.assertEqual([], service.threadpool.threads)
        self.assertFalse(service.websocket.listener.connected())
