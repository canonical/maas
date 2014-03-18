# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom test-case classes."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'MAASServerTestCase',
    'SeleniumTestCase',
    'TestWithoutCrochetMixin',
    ]

import SocketServer
import threading
from unittest import SkipTest
import wsgiref

import crochet
import django
from django.core.cache import cache as django_cache
from django.core.urlresolvers import reverse
from django.db import connection
from django.test.client import encode_multipart
from fixtures import Fixture
from maasserver.clusterrpc import power_parameters
from maasserver.fields import register_mac_type
from maasserver.testing.factory import factory
from maastesting.celery import CeleryFixture
from maastesting.djangotestcase import (
    cleanup_db,
    DjangoTestCase,
    )
from maastesting.fixtures import DisplayFixture
from maastesting.testcase import MAASTestCase
from mock import Mock
import provisioningserver
from provisioningserver.testing.tags import TagCachedKnowledgeFixture
from provisioningserver.testing.worker_cache import WorkerCacheFixture
from subunit import run_isolated


MIME_BOUNDARY = 'BoUnDaRyStRiNg'
MULTIPART_CONTENT = 'multipart/form-data; boundary=%s' % MIME_BOUNDARY


class MAASServerTestCase(DjangoTestCase):
    """:class:`TestCase` variant with the basics for maasserver testing.

    :ivar client: Django http test client.
    """

    @classmethod
    def setUpClass(cls):
        register_mac_type(connection.cursor())

    def setUp(self):
        super(MAASServerTestCase, self).setUp()
        self.useFixture(WorkerCacheFixture())
        self.useFixture(TagCachedKnowledgeFixture())
        self.addCleanup(django_cache.clear)
        self.celery = self.useFixture(CeleryFixture())
        # This patch prevents communication with a non-existent cluster
        # controller when fetching power types.
        static_params = (
            provisioningserver.power_schema.JSON_POWER_TYPE_PARAMETERS)
        self.patch(
            power_parameters,
            'get_all_power_types_from_clusters').return_value = static_params

    def client_log_in(self, as_admin=False):
        """Log `self.client` into MAAS.

        Sets `self.logged_in_user` to match the logged-in identity.
        """
        password = 'test'
        if as_admin:
            user = factory.make_admin(password=password)
        else:
            user = factory.make_user(password=password)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user

    def client_put(self, path, data=None):
        """Perform an HTTP PUT on the Django test client.

        This wraps `self.client.put` in a way that's both convenient and
        compatible across Django versions.  It accepts a dict of data to
        be sent as part of the request body, in MIME multipart encoding.
        """
        # Since Django 1.5, client.put() requires data in the form of a
        # string.  The application (that's us) should take care of MIME
        # encoding.
        # The details of that MIME encoding were ripped off from the Django
        # test client code.
        if data is None:
            return self.client.put(path)
        else:
            return self.client.put(
                path, encode_multipart(MIME_BOUNDARY, data), MULTIPART_CONTENT)


# Django supports Selenium tests only since version 1.4.
django_supports_selenium = (django.VERSION >= (1, 4))

if django_supports_selenium:
    from django.test import LiveServerTestCase
    from selenium.webdriver.firefox.webdriver import WebDriver
else:
    LiveServerTestCase = object  # noqa


class LogSilencerFixture(Fixture):

    old_handle_error = wsgiref.handlers.BaseHandler.handle_error
    old_log_exception = wsgiref.handlers.BaseHandler.log_exception

    def setUp(self):
        super(LogSilencerFixture, self).setUp()
        self.silence_loggers()
        self.addCleanup(self.unsilence_loggers)

    def silence_loggers(self):
        # Silence logging of errors to avoid the
        # "IOError: [Errno 32] Broken pipe" error.
        SocketServer.BaseServer.handle_error = Mock()
        wsgiref.handlers.BaseHandler.log_exception = Mock()

    def unsilence_loggers(self):
        """Restore original handle_error/log_exception methods."""
        SocketServer.BaseServer.handle_error = self.old_handle_error
        wsgiref.handlers.BaseHandler.log_exception = self.old_log_exception


class SeleniumTestCase(MAASTestCase, LiveServerTestCase):
    """Selenium-enabled test case.

    Two users are pre-created: "user" for a regular user account, or "admin"
    for an administrator account.  Both have the password "test".  You can log
    in as either using `log_in`.
    """

    # Load the selenium test fixture.
    fixtures = ['selenium_tests_fixture.yaml']

    @classmethod
    def setUpClass(cls):
        if not django_supports_selenium:
            return
        cls.display = DisplayFixture()
        cls.display.__enter__()

        cls.silencer = LogSilencerFixture()
        cls.silencer.__enter__()

        cls.selenium = WebDriver()
        super(SeleniumTestCase, cls).setUpClass()

    def setUp(self):
        if not django_supports_selenium:
            raise SkipTest(
                "Live tests only enabled if Django.version >=1.4.")
        super(SeleniumTestCase, self).setUp()

    def tearDown(self):
        super(SeleniumTestCase, self).tearDown()
        cleanup_db(self)
        django_cache.clear()

    @classmethod
    def tearDownClass(cls):
        if not django_supports_selenium:
            return
        cls.selenium.quit()
        cls.display.__exit__(None, None, None)
        cls.silencer.__exit__(None, None, None)
        super(SeleniumTestCase, cls).tearDownClass()

    def log_in(self, user='user', password='test'):
        """Log in as the given user.  Defaults to non-admin user."""
        self.get_page('login')
        username_input = self.selenium.find_element_by_id("id_username")
        username_input.send_keys(user)
        password_input = self.selenium.find_element_by_id("id_password")
        password_input.send_keys(password)
        self.selenium.find_element_by_xpath('//input[@value="Login"]').click()

    def get_page(self, *reverse_args, **reverse_kwargs):
        """GET a page.  Arguments are passed on to `reverse`."""
        path = reverse(*reverse_args, **reverse_kwargs)
        return self.selenium.get("%s%s" % (self.live_server_url, path))


class TestWithoutCrochetMixin:
    """Ensure that Crochet's event-loop is not running.

    Crochet's event-loop cannot easily be resurrected, so this runs each
    test in a new subprocess. There we can stop Crochet without worrying
    about how to get it going again.

    Use this where tests must, for example, patch out global state
    during testing, where those patches coincide with things that
    Crochet expects to use too, ``time.sleep`` for example.
    """

    _dead_thread = threading.Thread()
    _dead_thread.start()
    _dead_thread.join()

    def __call__(self, result=None):
        if result is None:
            result = self.defaultTestResult()
        # nose.proxy.ResultProxy.assertMyTest() is weird, and makes
        # things break, so we neutralise it here.
        result.assertMyTest = lambda test: None
        # Finally, run the test in a subprocess.
        up = super(TestWithoutCrochetMixin, self.__class__)
        run_isolated(up, self, result)

    run = __call__

    def setUp(self):
        super(TestWithoutCrochetMixin, self).setUp()
        # Ensure that Crochet's event-loop has shutdown. The following
        # runs in the child process started by run_isolated() so we
        # don't need to repair the damage we do.
        if crochet._watchdog.is_alive():
            crochet._watchdog._canary = self._dead_thread
            crochet._watchdog.join()  # Wait for the watchdog to stop.
            self.assertFalse(crochet.reactor.running)
