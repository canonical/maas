# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom test-case classes."""

__all__ = [
    'MAASServerTestCase',
    'MAASTransactionServerTestCase',
    'SeleniumTestCase',
    'SerializationFailureTestCase',
    'TestWithoutCrochetMixin',
    'UniqueViolationTestCase',
    ]

from itertools import count
import socketserver
import sys
import threading
from unittest import SkipTest
from unittest.mock import Mock
import warnings
import wsgiref

import crochet
import django
from django.core.urlresolvers import reverse
from django.db import (
    close_old_connections,
    connection,
    transaction,
)
from django.db.utils import (
    IntegrityError,
    OperationalError,
)
from fixtures import Fixture
from maasserver.fields import register_mac_type
from maasserver.testing.factory import factory
from maasserver.testing.fixtures import (
    IntroCompletedFixture,
    PackageRepositoryFixture,
)
from maasserver.testing.orm import PostCommitHooksTestMixin
from maasserver.testing.testclient import MAASSensibleClient
from maasserver.utils.orm import (
    is_serialization_failure,
    is_unique_violation,
)
from maastesting.djangotestcase import (
    DjangoTestCase,
    DjangoTransactionTestCase,
)
from maastesting.fixtures import DisplayFixture
from maastesting.utils import run_isolated


class MAASRegionTestCaseBase(PostCommitHooksTestMixin):
    """Base test case for testing the region.

    See sub-classes for the real deal though.
    """

    client_class = MAASSensibleClient

    # For each piece of default data introduced via migrations we need
    # to also include a data fixture. This needs to be representative,
    # but can be a reduced set.
    fixtures = []

    @classmethod
    def setUpClass(cls):
        super(MAASRegionTestCaseBase, cls).setUpClass()
        register_mac_type(connection.cursor())

    def setUp(self):
        super(MAASRegionTestCaseBase, self).setUp()

        # Avoid circular imports.
        from maasserver.models import signals

        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        from maasserver.clusterrpc.testing import driver_parameters
        self.useFixture(driver_parameters.StaticDriverTypesFixture())
        self.useFixture(PackageRepositoryFixture())
        self.useFixture(IntroCompletedFixture())

        # XXX: allenap bug=1427628 2015-03-03: These should not be here.
        # Disconnect the status transition event to speed up tests.
        self.patch(signals.events, 'STATE_TRANSITION_EVENT_CONNECT', False)

    def client_log_in(self, as_admin=False, completed_intro=True):
        """Log `self.client` into MAAS.

        Sets `self.logged_in_user` to match the logged-in identity.
        """
        warnings.warn(
            "client_log_in assumes that the client uses password "
            "authentication, but this is not always the case. Use "
            "client.login instead.", DeprecationWarning)
        password = 'test'
        if as_admin:
            user = factory.make_admin(
                password=password, completed_intro=completed_intro)
        else:
            user = factory.make_User(
                password=password, completed_intro=completed_intro)
        self.client.login(username=user.username, password=password)
        self.logged_in_user = user


class MAASServerTestCase(
        MAASRegionTestCaseBase, DjangoTestCase):
    """:class:`TestCase` variant for region testing."""


class MAASTransactionServerTestCase(
        MAASRegionTestCaseBase, DjangoTransactionTestCase):
    """:class:`TestCase` variant for *transaction* region testing."""


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
        socketserver.BaseServer.handle_error = Mock()
        wsgiref.handlers.BaseHandler.log_exception = Mock()

    def unsilence_loggers(self):
        """Restore original handle_error/log_exception methods."""
        socketserver.BaseServer.handle_error = self.old_handle_error
        wsgiref.handlers.BaseHandler.log_exception = self.old_log_exception


class SeleniumTestCase(
        DjangoTransactionTestCase, LiveServerTestCase,
        PostCommitHooksTestMixin):
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


class SerializationFailureTestCase(
        DjangoTransactionTestCase, PostCommitHooksTestMixin):

    def create_stest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS stest (a INTEGER)")

    def drop_stest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS stest")

    def setUp(self):
        super(SerializationFailureTestCase, self).setUp()
        self.create_stest_table()
        # Put something into the stest table upon which to trigger a
        # serialization failure.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO stest VALUES (1)")

    def tearDown(self):
        super(SerializationFailureTestCase, self).tearDown()
        self.drop_stest_table()

    def cause_serialization_failure(self):
        """Trigger an honest, from the database, serialization failure."""
        # Helper to switch the transaction to SERIALIZABLE.
        def set_serializable():
            with connection.cursor() as cursor:
                cursor.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")

        # Perform a conflicting update. This must run in a separate thread. It
        # also must begin after the beginning of the transaction in which we
        # will trigger a serialization failure AND commit before that other
        # transaction commits. This doesn't need to run with serializable
        # isolation.
        def do_conflicting_update():
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute("UPDATE stest SET a = 2")
            finally:
                close_old_connections()

        def trigger_serialization_failure():
            # Fetch something first. This ensures that we're inside the
            # transaction, and that the database has a reference point for
            # calculating serialization failures.
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM stest")
                cursor.fetchall()

            # Run do_conflicting_update() in a separate thread.
            thread = threading.Thread(target=do_conflicting_update)
            thread.start()
            thread.join()

            # Updating the same rows as do_conflicting_update() did will
            # trigger a serialization failure. We have to check the __cause__
            # to confirm the failure type as reported by PostgreSQL.
            with connection.cursor() as cursor:
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


class UniqueViolationTestCase(
        DjangoTransactionTestCase, PostCommitHooksTestMixin):

    def create_uvtest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS uvtest")
            cursor.execute("CREATE TABLE uvtest (a INTEGER PRIMARY KEY)")

    def drop_uvtest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS uvtest")

    def setUp(self):
        super(UniqueViolationTestCase, self).setUp()
        self.conflicting_values = count(1)
        self.create_uvtest_table()

    def tearDown(self):
        super(UniqueViolationTestCase, self).tearDown()
        self.drop_uvtest_table()

    def cause_unique_violation(self):
        """Trigger an honest, from the database, unique violation.

        This may appear needlessly elaborate, but it's for a good reason.
        Indexes in PostgreSQL are a bit weird; they don't fully support MVCC
        so it's possible for situations like the following:

          CREATE TABLE foo (id SERIAL PRIMARY KEY);
          -- Session A:
          BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
          INSERT INTO foo (id) VALUES (1);
          -- Session B:
          BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ;
          SELECT id FROM foo;  -- Nothing.
          INSERT INTO foo (id) VALUES (1);  -- Hangs.
          -- Session A:
          COMMIT;
          -- Session B:
          ERROR:  duplicate key value violates unique constraint "..."
          DETAIL:  Key (id)=(1) already exists.

        Two things to note:

          1. Session B hangs when there's a potential conflict on id's index.

          2. Session B fails with a duplicate key error.

        Both differ from expectations:

          1. I would expect the transaction to continue optimistically and
             only fail if session A commits.

          2. I would expect a serialisation failure instead.

        This method jumps through hoops to reproduce the situation above so
        that we're testing against PostgreSQL's exact behaviour as of today,
        not the behaviour that we observed at a single moment in time.
        PostgreSQL may change its behaviour in later versions and this test
        ought to tell us about it.

        """
        # Helper to switch the transaction to REPEATABLE READ.
        def set_repeatable_read():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET TRANSACTION ISOLATION LEVEL "
                    "REPEATABLE READ")

        # Both threads / database sessions will attempt to insert this.
        conflicting_value = next(self.conflicting_values)

        # Perform a conflicting insert. This must run in a separate thread. It
        # also must begin after the beginning of the transaction in which we
        # will trigger a unique violation AND commit before that other
        # transaction commits. This doesn't need to run with any special
        # isolation; it just needs to be in a transaction.
        def do_conflicting_insert():
            try:
                with transaction.atomic():
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "INSERT INTO uvtest VALUES (%s)",
                            [conflicting_value])
            finally:
                close_old_connections()

        def trigger_unique_violation():
            # Fetch something first. This ensures that we're inside the
            # transaction, and so the database has a reference point for
            # repeatable reads.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM uvtest WHERE a = %s",
                    [conflicting_value])
                self.assertIsNone(cursor.fetchone(), (
                    "We've seen through PostgreSQL impenetrable transaction "
                    "isolation — or so we once thought — to witness a "
                    "conflicting value from another database session. "
                    "Needless to say, this requires investigation."))

            # Run do_conflicting_insert() in a separate thread and wait for it
            # to commit and return.
            thread = threading.Thread(target=do_conflicting_insert)
            thread.start()
            thread.join()

            # Still no sign of that conflicting value from here.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM uvtest WHERE a = %s",
                    [conflicting_value])
                self.assertIsNone(cursor.fetchone(), (
                    "PostgreSQL, once thought of highly in transactional "
                    "circles, has dropped its kimono and disgraced itself "
                    "with its wanton exhibition of conflicting values from "
                    "another's session."))

            # Inserting the same row will trigger a unique violation.
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO uvtest VALUES (%s)",
                    [conflicting_value])

        if connection.in_atomic_block:
            # We're already in a transaction.
            set_repeatable_read()
            trigger_unique_violation()
        else:
            # Start a transaction in this thread.
            with transaction.atomic():
                set_repeatable_read()
                trigger_unique_violation()

    def capture_unique_violation(self):
        """Trigger a unique violation, return its ``exc_info`` tuple."""
        try:
            self.cause_unique_violation()
        except IntegrityError as e:
            if is_unique_violation(e):
                return sys.exc_info()
            else:
                raise
