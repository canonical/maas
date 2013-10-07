# Copyright 2012, 2013 Canonical Ltd.  This software is licensed under the
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
    'AdminLoggedInTestCase',
    'LoggedInTestCase',
    'MAASTestCase',
    ]

import SocketServer
from unittest import SkipTest
import wsgiref

import django
from django.core.cache import cache as django_cache
from django.core.urlresolvers import reverse
from django.db import connection
from django.test.client import encode_multipart
from fixtures import Fixture
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
from provisioningserver.testing.tags import TagCachedKnowledgeFixture
from provisioningserver.testing.worker_cache import WorkerCacheFixture


MIME_BOUNDARY = 'BoUnDaRyStRiNg'
MULTIPART_CONTENT = 'multipart/form-data; boundary=%s' % MIME_BOUNDARY


class MAASServerTestCase(DjangoTestCase):
    """:class:`TestCase` variant with the basics for maasserver testing."""

    @classmethod
    def setUpClass(cls):
        register_mac_type(connection.cursor())

    def setUp(self):
        super(MAASServerTestCase, self).setUp()
        self.useFixture(WorkerCacheFixture())
        self.useFixture(TagCachedKnowledgeFixture())
        self.addCleanup(django_cache.clear)
        self.celery = self.useFixture(CeleryFixture())

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


class LoggedInTestCase(MAASServerTestCase):
    """:class:`MAASServerTestCase` variant with a logged-in web client.

    :ivar client: Django http test client, logged in for MAAS access.
    :ivar logged_in_user: User identity that `client` is authenticated for.
    """

    def setUp(self):
        super(LoggedInTestCase, self).setUp()
        self.logged_in_user_password = 'test'
        self.logged_in_user = factory.make_user(
            password=self.logged_in_user_password)
        self.client.login(
            username=self.logged_in_user.username,
            password=self.logged_in_user_password)

    def become_admin(self):
        """Promote the logged-in user to admin."""
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()


class AdminLoggedInTestCase(LoggedInTestCase):
    """:class:`LoggedInTestCase` variant that is logged in as an admin."""

    def setUp(self):
        super(AdminLoggedInTestCase, self).setUp()
        self.become_admin()


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


class SeleniumLoggedInTestCase(MAASTestCase, LiveServerTestCase):

    # Load the selenium test fixture.
    # admin user: username=admin/pw=test
    # normal user: username=user/pw=test
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
        super(SeleniumLoggedInTestCase, cls).setUpClass()

    def login(self):
        self.selenium.get('%s%s' % (self.live_server_url, reverse('login')))
        username_input = self.selenium.find_element_by_id("id_username")
        username_input.send_keys('user')
        password_input = self.selenium.find_element_by_id("id_password")
        password_input.send_keys('test')
        self.selenium.find_element_by_xpath('//input[@value="Login"]').click()

    def setUp(self):
        if not django_supports_selenium:
            raise SkipTest(
                "Live tests only enabled if Django.version >=1.4.")
        super(SeleniumLoggedInTestCase, self).setUp()
        self.login()

    def tearDown(self):
        super(SeleniumLoggedInTestCase, self).tearDown()
        cleanup_db(self)
        django_cache.clear()

    @classmethod
    def tearDownClass(cls):
        if not django_supports_selenium:
            return
        cls.selenium.quit()
        cls.display.__exit__(None, None, None)
        cls.silencer.__exit__(None, None, None)
        super(SeleniumLoggedInTestCase, cls).tearDownClass()
