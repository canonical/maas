# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""maasserver fixtures."""

import inspect
import logging

from django.db import connection
import fixtures

from maasserver.models import Config, user
from maasserver.rbac import FakeRBACClient, rbac
from maasserver.secrets import SecretManager
from maasserver.testing.factory import factory


class PackageRepositoryFixture(fixtures.Fixture):
    """Insert the base PackageRepository entries."""

    def _setUp(self):
        factory.make_default_PackageRepositories()


class IntroCompletedFixture(fixtures.Fixture):
    """Mark intro as completed as default."""

    def _setUp(self):
        Config.objects.set_config("completed_intro", True)


class StacktraceFilter(logging.Filter):
    """Injects stack trace information when added as a filter to a logger."""

    def filter(self, record):
        source_trace = ""
        stack = inspect.stack()
        for s in reversed(stack):
            line = s[2]
            file = "/".join(s[1].split("/")[-3:])
            calling_method = s[3]
            source_trace += f"{line} in {file} at {calling_method}\n"
        record.sourcetrace = source_trace
        del stack
        return True


class LogSQL(fixtures.Fixture):
    """Logs SQL to standard out.

    This should only be used for debugging a single test. It should never
    land in trunk on an actual test.
    """

    def __init__(self, include_stacktrace=False):
        super().__init__()
        self.include_stacktrace = include_stacktrace

    def _setUp(self):
        log = logging.getLogger("django.db.backends")
        self._origLevel = log.level
        self._setHandler = logging.StreamHandler()
        if self.include_stacktrace:
            self._addedFilter = StacktraceFilter()
            log.addFilter(self._addedFilter)
            self._setHandler.setFormatter(
                logging.Formatter(
                    "-" * 80 + "\n%(sql)s\n\nStacktrace of SQL query "
                    "producer:\n%(sourcetrace)s" + "-" * 80 + "\n"
                )
            )
        log.setLevel(logging.DEBUG)
        log.addHandler(self._setHandler)

    def _tearDown(self):
        log = logging.getLogger("django.db.backends")
        log.setLevel(self._origLevel)
        if self.include_stacktrace:
            log.removeFilter(self._addedFilter)
        self.removeHandler(self._setHandler)


class RBACClearFixture(fixtures.Fixture):
    """Fixture that clears the RBAC thread-local cache between tests."""

    def _setUp(self):
        self.addCleanup(rbac.clear)


class RBACForceOffFixture(fixtures.Fixture):
    """Fixture that ensures RBAC is off and no query is performed.

    This is great for tests that count queries and ensure that one is
    not caused.
    """

    def _setUp(self):
        orig_get_url = rbac._get_rbac_url
        rbac._get_rbac_url = lambda: None

        def cleanup():
            rbac._get_rbac_url = orig_get_url

        self.addCleanup(cleanup)


class RBACEnabled(fixtures.Fixture):
    """Fixture that enables RBAC."""

    def _setUp(self):
        # Must be called inside a transaction.
        assert connection.in_atomic_block

        SecretManager().set_composite_secret(
            "external-auth",
            {
                "url": "https://auth.example.com",
                "user": "user@candid",
                "key": "x0NeASLPFhOFfq3Q9M0joMveI4HjGwEuJ9dtX/HTSRY=",
                "rbac-url": "http://rbac.example.com",
            },
        )

        client = FakeRBACClient()
        rbac._store.client = client
        rbac._store.cleared = False
        self.store = client.store

        def cleanup():
            rbac._store.client = None
            rbac.clear()

        self.addCleanup(cleanup)


class UserSkipCreateAuthorisationTokenFixture(fixtures.Fixture):
    """Prevents the automatic authorisation token creation on user create."""

    def _setUp(self):
        user.SKIP_CREATE_AUTHORISATION_TOKEN = True

        def cleanup():
            user.SKIP_CREATE_AUTHORISATION_TOKEN = False

        self.addCleanup(cleanup)
