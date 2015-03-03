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
    'SerializationFailureTestCase',
    'TestWithoutCrochetMixin',
    ]

from contextlib import closing
import SocketServer
import sys
import threading
from unittest import SkipTest
import wsgiref

import crochet
import django
from django.core.urlresolvers import reverse
from django.db import (
    connection,
    transaction,
    )
from django.db.utils import OperationalError
from django.test.client import encode_multipart
from fixtures import Fixture
from maasserver.clusterrpc import power_parameters
from maasserver.fields import register_mac_type
from maasserver.testing.factory import factory
from maasserver.utils.orm import is_serialization_failure
from maastesting.djangotestcase import (
    DjangoTestCase,
    DjangoTransactionTestCase,
    )
from maastesting.fixtures import DisplayFixture
from maastesting.utils import run_isolated
from mock import Mock
import provisioningserver


MIME_BOUNDARY = 'BoUnDaRyStRiNg'
MULTIPART_CONTENT = 'multipart/form-data; boundary=%s' % MIME_BOUNDARY


class MAASServerTestCase(DjangoTestCase):
    """:class:`TestCase` variant with the basics for maasserver testing.

    :ivar client: Django http test client.
    """

    # For each piece of default data introduced via migrations we need
    # to also include a data fixture. This needs to be representative,
    # but can be a reduced set.
    fixtures = [
        "candidatenames.yaml",
        "defaultzone.yaml",
    ]

    @classmethod
    def setUpClass(cls):
        super(MAASServerTestCase, cls).setUpClass()
        register_mac_type(connection.cursor())

    def setUp(self):
        super(MAASServerTestCase, self).setUp()

        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        # This patch prevents communication with a non-existent cluster
        # controller when fetching power types.
        static_params = (
            provisioningserver.power_schema.JSON_POWER_TYPE_PARAMETERS)
        self.patch(
            power_parameters,
            'get_all_power_types_from_clusters').return_value = static_params

        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        # Disconnect the monitor cancellation as it's triggered by a signal.
        # Avoid circular imports.
        from maasserver import monitor_connect
        self.patch(monitor_connect, 'MONITOR_CANCEL_CONNECT', False)

        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        # Disconnect the status transition event to speed up tests.
        # Avoid circular imports.
        from maasserver import event_connect
        self.patch(event_connect, 'STATE_TRANSITION_EVENT_CONNECT', False)

    def client_log_in(self, as_admin=False):
        """Log `self.client` into MAAS.

        Sets `self.logged_in_user` to match the logged-in identity.
        """
        password = 'test'
        if as_admin:
            user = factory.make_admin(password=password)
        else:
            user = factory.make_User(password=password)
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


class SeleniumTestCase(DjangoTransactionTestCase, LiveServerTestCase):
    """Selenium-enabled test case.

    Two users are pre-created: "user" for a regular user account, or "admin"
    for an administrator account.  Both have the password "test".  You can log
    in as either using `log_in`.
    """

    # Load the selenium test fixture.
    fixtures = ['src/maastesting/protractor/fixture.yaml']

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


class SerializationFailureTestCase(DjangoTransactionTestCase):

    def create_stest_table(self):
        with closing(connection.cursor()) as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS stest (a INTEGER)")

    def drop_stest_table(self):
        with closing(connection.cursor()) as cursor:
            cursor.execute("DROP TABLE IF EXISTS stest")

    def setUp(self):
        super(SerializationFailureTestCase, self).setUp()
        self.create_stest_table()
        # Put something into the stest table upon which to trigger a
        # serialization failure.
        with transaction.atomic():
            with closing(connection.cursor()) as cursor:
                cursor.execute("INSERT INTO stest VALUES (1)")

    def tearDown(self):
        super(SerializationFailureTestCase, self).tearDown()
        self.drop_stest_table()

    def cause_serialization_failure(self):
        """Trigger an honest, from the database, serialization failure."""
        # Helper to switch the transaction to SERIALIZABLE.
        def set_serializable():
            with closing(connection.cursor()) as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

        # Perform a conflicting update. This must run in a separate thread. It
        # also must begin after the beginning of the transaction in which we
        # will trigger a serialization failure AND commit before that other
        # transaction commits. This doesn't need to run with serializable
        # isolation.
        def do_conflicting_update():
            with transaction.atomic():
                with closing(connection.cursor()) as cursor:
                    cursor.execute("UPDATE stest SET a = 2")

        def trigger_serialization_failure():
            # Fetch something first. This ensures that we're inside the
            # transaction, and that the database has a reference point for
            # calculating serialization failures.
            with closing(connection.cursor()) as cursor:
                cursor.execute("SELECT * FROM stest")
                cursor.fetchall()

            # Run do_conflicting_update() in a separate thread.
            thread = threading.Thread(target=do_conflicting_update)
            thread.start()
            thread.join()

            # Updating the same rows as do_conflicting_update() did will
            # trigger a serialization failure. We have to check the __cause__
            # to confirm the failure type as reported by PostgreSQL.
            with closing(connection.cursor()) as cursor:
                cursor.execute("UPDATE stest SET a = 4")

        if connection.in_atomic_block:
            # We're already in a transaction.
            set_serializable()
            trigger_serialization_failure()
        else:
            # Start a transaction in this thread.
            with transaction.atomic():
                set_serializable()
                trigger_serialization_failure()

    def capture_serialization_failure(self):
        """Trigger a serialization failure, return its ``exc_info`` tuple."""
        try:
            self.cause_serialization_failure()
        except OperationalError as e:
            if is_serialization_failure(e):
                return sys.exc_info()
            else:
                raise
