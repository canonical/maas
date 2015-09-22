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

import random
from textwrap import dedent

from django.core.handlers.wsgi import WSGIHandler
from lxml import html
from maasserver import (
    eventloop,
    start_up,
    webapp,
)
from maasserver.websockets.protocol import WebSocketFactory
from maastesting.factory import factory
from maastesting.matchers import (
    DocTestMatches,
    MockCalledOnceWith,
)
from maastesting.testcase import MAASTestCase
from maastesting.twisted import TwistedLoggerFixture
from mock import sentinel
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
from twisted.web.resource import Resource
from twisted.web.server import Site
from twisted.web.test.requesthelper import DummyRequest


class TestCleanPathRequest(MAASTestCase):

    def test_requestReceived_converts_extra_slashes_to_single(self):
        mock_super_requestReceived = self.patch(
            webapp.Request, "requestReceived")
        request = webapp.CleanPathRequest(sentinel.channel, sentinel.queued)
        path_pieces = [
            factory.make_name("path")
            for _ in range(3)
            ]
        double_path = ("/" * random.randint(2, 8)).join(path_pieces)
        single_path = "/".join(path_pieces)
        request.requestReceived(
            sentinel.command, double_path, sentinel.version)
        self.assertThat(
            mock_super_requestReceived,
            MockCalledOnceWith(
                sentinel.command, single_path, sentinel.version))

    def test_requestReceived_converts_extra_slashes_ignores_args(self):
        mock_super_requestReceived = self.patch(
            webapp.Request, "requestReceived")
        request = webapp.CleanPathRequest(sentinel.channel, sentinel.queued)
        path_pieces = [
            factory.make_name("path")
            for _ in range(3)
            ]
        args = "?op=extra//data"
        double_path = ("/" * random.randint(2, 8)).join(path_pieces) + args
        single_path = "/".join(path_pieces) + args
        request.requestReceived(
            sentinel.command, double_path, sentinel.version)
        self.assertThat(
            mock_super_requestReceived,
            MockCalledOnceWith(
                sentinel.command, single_path, sentinel.version))


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
        # Patch the getServiceNamed so the WebSocketFactory does not
        # error trying to register for events from the RPC service. In this
        # test the RPC service is not started.
        self.patch(eventloop.services, "getServiceNamed")
        return service

    def test__init_creates_site(self):
        service = self.make_webapp()
        self.assertThat(service.site, IsInstance(Site))
        self.assertThat(
            service.site.requestFactory, Is(webapp.CleanPathRequest))
        self.assertThat(service.websocket, IsInstance(WebSocketFactory))

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

    def test__startService_starts_websocket_and_application(self):
        service = self.make_webapp()
        self.addCleanup(service.stopService)

        # start_up() isn't safe to call right now, but we only really care
        # that it is called.
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.succeed(None)

        service.startService()

        self.assertTrue(service.running)
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

    def test__stopService_stops_the_service_and_the_websocket(self):
        service = self.make_webapp()
        self.patch_autospec(start_up, "start_up")
        start_up.start_up.return_value = defer.succeed(None)

        with TwistedLoggerFixture() as logger:
            service.startService()

        self.expectThat(
            logger.output, DocTestMatches("""\
            Site starting on ...
            ---
            Listening for notificaton from database.
            """))

        with TwistedLoggerFixture() as logger:
            service.stopService()

        self.expectThat(
            logger.output, DocTestMatches("""\
            (TCP Port ... Closed)
            """))

        self.assertFalse(service.running)
        self.assertFalse(service.websocket.listener.connected())
