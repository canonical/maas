# Copyright 2013-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for API testing."""
from maasserver.testing.testclient import MAASSensibleClient


__all__ = [
    'APITestCase',
    'APITransactionTestCase',
    'explain_unexpected_response',
    'log_in_as_normal_user',
    'make_worker_client',
    'MultipleUsersScenarios',
    ]

from abc import (
    ABCMeta,
    abstractproperty,
)

from maasserver.testing.factory import factory
from maasserver.testing.oauthclient import OAuthAuthenticatedClient
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.utils.orm import transactional
from maastesting.testcase import MAASTestCase
from metadataserver.models.nodekey import NodeKey
from metadataserver.nodeinituser import get_node_init_user


class MultipleUsersScenarios(metaclass=ABCMeta):
    """A mixin that uses testscenarios to repeat a testcase as different
    users.

    The scenarios should inject a `userfactory` variable that will
    be called to produce the user used in the tests e.g.:

    class ExampleTest(MultipleUsersScenarios, MAASServerTestCase):
        scenarios = [
            ('anon', dict(userfactory=lambda: AnonymousUser())),
            ('user', dict(userfactory=factory.make_User)),
            ('admin', dict(userfactory=factory.make_admin)),
            ]

        def test_something(self):
            pass

    The test `test_something` with be run 3 times: one with a anonymous user
    logged in, once with a simple (non-admin) user logged in and once with
    an admin user logged in.
    """

    scenarios = abstractproperty(
        "The scenarios as defined by testscenarios.")

    def setUp(self):
        super(MultipleUsersScenarios, self).setUp()
        user = self.userfactory()
        if not user.is_anonymous():
            password = factory.make_string()
            user.set_password(password)
            user.save()
            self.logged_in_user = user
            self.client.login(
                username=self.logged_in_user.username, password=password)


class APITestCaseBase(MAASTestCase):
    """Base class for logged-in API tests.

    :ivar logged_in_user: A user who is currently logged in and can access
        the API.
    :ivar client: Authenticated API client (unsurprisingly, logged in as
        `logged_in_user`).
    """

    @transactional
    def setUp(self):
        super(APITestCaseBase, self).setUp()
        self.logged_in_user = factory.make_User()
        self.client = OAuthAuthenticatedClient(self.logged_in_user)

    @transactional
    def become_admin(self):
        """Promote the logged-in user to admin."""
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()

    @transactional
    def logout(self):
        """Promote the logged-in user to admin."""
        self.logged_in_user = None
        self.client = MAASSensibleClient()

    def assertResponseCode(self, expected_code, response):
        if response.status_code != expected_code:
            self.fail("Expected %s response, got %s:\n%s" % (
                expected_code, response.status_code, response.content))


class APITestCase(APITestCaseBase, MAASServerTestCase):
    """Class for logged-in API tests within a single transaction."""


class APITransactionTestCase(APITestCaseBase, MAASTransactionServerTestCase):
    """Class for logged-in API tests with the ability to use transactions."""


def log_in_as_normal_user(client):
    """Log `client` in as a normal user."""
    password = factory.make_string()
    user = factory.make_User(password=password)
    client.login(username=user.username, password=password)
    return user


def make_worker_client(rack_controller):
    """Create a test client logged in as if it were `rack_controller`."""
    token = NodeKey.objects.get_token_for_node(rack_controller)
    return OAuthAuthenticatedClient(
        get_node_init_user(), token=token)


def explain_unexpected_response(expected_status, response):
    """Return human-readable failure message: unexpected http response."""
    return "Unexpected http status (expected %s): %s - %s" % (
        expected_status,
        response.status_code,
        response.content,
        )
