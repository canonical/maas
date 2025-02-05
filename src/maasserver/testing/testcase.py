# Copyright 2012-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom test-case classes."""

__all__ = [
    "MAASLegacyServerTestCase",
    "MAASLegacyTransactionServerTestCase",
    "MAASServerTestCase",
    "MAASTransactionServerTestCase",
    "SerializationFailureTestCase",
    "UniqueViolationTestCase",
]

from itertools import count
import os
import sys
import threading
from unittest.util import strclass

from django.db import (
    close_old_connections,
    connection,
    reset_queries,
    transaction,
)
from django.db.utils import IntegrityError, OperationalError

from maasserver.models import dhcpsnippet as snippet_module
from maasserver.models import interface as interface_module
from maasserver.models import iprange as iprange_module
from maasserver.models import node as node_module
from maasserver.models import signals
from maasserver.models import staticipaddress as staticipaddress_module
from maasserver.models import subnet as subnet_module
from maasserver.models import vlan as vlan_module
from maasserver.testing.fixtures import (
    IntroCompletedFixture,
    PackageRepositoryFixture,
    RBACClearFixture,
)
from maasserver.testing.orm import PostCommitHooksTestMixin
from maasserver.testing.resources import DjangoDatabasesManager
from maasserver.testing.testclient import MAASSensibleClient
from maasserver.utils.orm import is_serialization_failure, is_unique_violation
from maastesting.djangotestcase import (
    DjangoTestCase,
    DjangoTransactionTestCase,
)
from maastesting.testcase import MAASTestCase


class MAASRegionTestCaseBase(PostCommitHooksTestMixin):
    """Base test case for testing the region.

    See sub-classes for the real deal though.
    """

    client_class = MAASSensibleClient

    # cache_boot_sources and delete_large_object_content_later are
    # called from signals and fire off threads to do work after the
    # commit. This can interfere with other tests, so we mock out,
    # post_commit_do for them, so they never will be called, unless the
    # tests explicitly sets these attributes to False.
    mock_cache_boot_source = True
    mock_delete_large_object_content_later = True

    @property
    def client(self):
        """Create a client on demand, and cache it.

        There are only a small number of tests that need this. They could
        probably all be migrated to use `APITestCase`'s features instead (and
        those of its descendants).
        """
        try:
            return self.__client
        except AttributeError:
            self.__client = self.client_class()
            return self.__client

    @client.setter
    def client(self, client):
        """Set the current client."""
        self.__client = client

    def setUp(self):
        reset_queries()  # Formerly this was handled by... Django?
        super().setUp()
        self._set_db_application_name()
        self.patch(node_module, "start_workflow")
        self.patch(vlan_module, "start_workflow")
        self.patch(subnet_module, "start_workflow")
        self.patch(iprange_module, "start_workflow")
        self.patch(staticipaddress_module, "start_workflow")
        self.patch(interface_module, "start_workflow")
        self.patch(snippet_module, "start_workflow")
        if self.mock_cache_boot_source:
            self.patch(signals.bootsources, "post_commit_do")

    def setUpFixtures(self):
        """This should be called by a subclass once other set-up is done."""
        # Avoid circular imports.
        from maasserver.models import signals

        # Always clear the RBAC thread-local between tests.
        self.useFixture(RBACClearFixture())

        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        self.useFixture(IntroCompletedFixture())

        # XXX: allenap bug=1427628 2015-03-03: These should not be here.
        # Disconnect the status transition event to speed up tests.
        self.patch(signals.events, "STATE_TRANSITION_EVENT_CONNECT", False)

    def assertNotInTransaction(self):
        self.assertFalse(
            connection.in_atomic_block,
            "Default connection is engaged in a transaction.",
        )

    def _set_db_application_name(self):
        """Set the application name to the current test, for debug."""
        testname = f"{strclass(self.__class__)}.{self._testMethodName}"
        with connection.cursor() as cursor:
            cursor.execute(f"SET application_name = '{testname}'")


class MAASLegacyServerTestCase(MAASRegionTestCaseBase, DjangoTestCase):
    """Legacy :class:`TestCase` variant for region testing.

    :deprecated: Do NOT use in new tests.
    """

    def setUp(self):
        super().setUp()
        self.setUpFixtures()

    def setUpFixtures(self):
        super().setUpFixtures()
        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        self.useFixture(PackageRepositoryFixture())


class MAASLegacyTransactionServerTestCase(
    MAASRegionTestCaseBase, DjangoTransactionTestCase
):
    """Legacy :class:`TestCase` variant for *transaction* region testing.

    :deprecated: Do NOT use in new tests.
    """

    def setUp(self):
        super().setUp()
        self.setUpFixtures()

    def setUpFixtures(self):
        super().setUpFixtures()
        # XXX: allenap bug=1427628 2015-03-03: This should not be here.
        self.useFixture(PackageRepositoryFixture())


class MAASServerTestCase(MAASRegionTestCaseBase, MAASTestCase):
    """:class:`TestCase` variant for region testing."""

    resources = (("databases", DjangoDatabasesManager(assume_dirty=False)),)

    # The database may be used in tests. See `MAASTestCase` for details.
    database_use_permitted = True

    def setUp(self):
        super().setUp()
        self.beginTransaction()
        self.addCleanup(self.endTransaction)
        self.setUpFixtures()
        if maas_data := os.getenv("MAAS_DATA"):
            os.mkdir(f"{maas_data}/image-storage")
        if maas_root := os.getenv("MAAS_ROOT"):
            os.mkdir(f"{maas_root}/certificates")

    def beginTransaction(self):
        """Begin new transaction using Django's `atomic`."""

        def fail_on_commit():
            raise AssertionError(
                "Tests using MAASServerTestCase aren't allowed to commit. "
                "Use MAASTransactionServerTestCase instead."
            )

        self.assertNotInTransaction()
        self.__atomic = transaction.atomic()
        self.__atomic.__enter__()
        # Fail if any test commits this transaction, since we want to
        # roll it back, so that the database can be reused.
        transaction.on_commit(fail_on_commit)

    def endTransaction(self):
        """Rollback transaction using Django's `atomic`."""
        transaction.set_rollback(True)
        self.__atomic.__exit__(None, None, None)
        self.assertNotInTransaction()


class MAASTransactionServerTestCase(MAASRegionTestCaseBase, MAASTestCase):
    """:class:`TestCase` variant for *transaction* region testing."""

    resources = (("databases", DjangoDatabasesManager(assume_dirty=True)),)

    # The database may be used in tests. See `MAASTestCase` for details.
    database_use_permitted = True

    def setUp(self):
        super().setUp()
        self.assertNotInTransaction()
        self.addCleanup(self.assertNotInTransaction)
        self.setUpFixtures()
        if maas_data := os.getenv("MAAS_DATA"):
            os.mkdir(f"{maas_data}/image-storage")
        if maas_root := os.getenv("MAAS_ROOT"):
            os.mkdir(f"{maas_root}/certificates")


class SerializationFailureTestCase(
    MAASTransactionServerTestCase, PostCommitHooksTestMixin
):
    def create_stest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("CREATE TABLE IF NOT EXISTS stest (a INTEGER)")

    def drop_stest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS stest")

    def setUp(self):
        super().setUp()
        self.create_stest_table()
        # Put something into the stest table upon which to trigger a
        # serialization failure.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("INSERT INTO stest VALUES (1)")

    def tearDown(self):
        super().tearDown()
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
    MAASTransactionServerTestCase, PostCommitHooksTestMixin
):
    def create_uvtest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS uvtest")
            cursor.execute("CREATE TABLE uvtest (a INTEGER PRIMARY KEY)")

    def drop_uvtest_table(self):
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS uvtest")

    def setUp(self):
        super().setUp()
        self.conflicting_values = count(1)
        self.create_uvtest_table()

    def tearDown(self):
        super().tearDown()
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
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"
                )

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
                            [conflicting_value],
                        )
            finally:
                close_old_connections()

        def trigger_unique_violation():
            # Fetch something first. This ensures that we're inside the
            # transaction, and so the database has a reference point for
            # repeatable reads.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM uvtest WHERE a = %s", [conflicting_value]
                )
                self.assertIsNone(
                    cursor.fetchone(),
                    (
                        "We've seen through PostgreSQL impenetrable transaction "
                        "isolation — or so we once thought — to witness a "
                        "conflicting value from another database session. "
                        "Needless to say, this requires investigation."
                    ),
                )

            # Run do_conflicting_insert() in a separate thread and wait for it
            # to commit and return.
            thread = threading.Thread(target=do_conflicting_insert)
            thread.start()
            thread.join()

            # Still no sign of that conflicting value from here.
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM uvtest WHERE a = %s", [conflicting_value]
                )
                self.assertIsNone(
                    cursor.fetchone(),
                    (
                        "PostgreSQL, once thought of highly in transactional "
                        "circles, has dropped its kimono and disgraced itself "
                        "with its wanton exhibition of conflicting values from "
                        "another's session."
                    ),
                )

            # Inserting the same row will trigger a unique violation.
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO uvtest VALUES (%s)", [conflicting_value]
                )

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
