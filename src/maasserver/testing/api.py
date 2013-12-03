# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for API testing."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'AnonAPITestCase',
    'APITestCase',
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
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.worker_user import get_worker_user


class AnonAPITestCase(MAASServerTestCase):
    """Base class for anonymous API tests."""


class MultipleUsersScenarios:
    """A mixin that uses testscenarios to repeat a testcase as different
    users.

    The scenarios should inject a `userfactory` variable that will
    be called to produce the user used in the tests e.g.:

    class ExampleTest(MultipleUsersScenarios, MAASServerTestCase):
        scenarios = [
            ('anon', dict(userfactory=lambda: AnonymousUser())),
            ('user', dict(userfactory=factory.make_user)),
            ('admin', dict(userfactory=factory.make_admin)),
            ]

        def test_something(self):
            pass

    The test `test_something` with be run 3 times: one with a anonymous user
    logged in, once with a simple (non-admin) user logged in and once with
    an admin user logged in.
    """

    __metaclass__ = ABCMeta

    scenarios = abstractproperty(
        "The scenarios as defined by testscenarios.")

    def setUp(self):
        super(MultipleUsersScenarios, self).setUp()
        user = self.userfactory()
        if not user.is_anonymous():
            password = factory.getRandomString()
            user.set_password(password)
            user.save()
            self.logged_in_user = user
            self.client.login(
                username=self.logged_in_user.username, password=password)


class APITestCase(MAASServerTestCase):
    """Base class for logged-in API tests.

    :ivar logged_in_user: A user who is currently logged in and can access
        the API.
    :ivar client: Authenticated API client (unsurprisingly, logged in as
        `logged_in_user`).
    """

    def setUp(self):
        super(APITestCase, self).setUp()
        self.logged_in_user = factory.make_user(
            username='test', password='test')
        self.client = OAuthAuthenticatedClient(self.logged_in_user)

    def become_admin(self):
        """Promote the logged-in user to admin."""
        self.logged_in_user.is_superuser = True
        self.logged_in_user.save()

    def assertResponseCode(self, expected_code, response):
        if response.status_code != expected_code:
            self.fail("Expected %s response, got %s:\n%s" % (
                expected_code, response.status_code, response.content))


def log_in_as_normal_user(client):
    """Log `client` in as a normal user."""
    password = factory.getRandomString()
    user = factory.make_user(password=password)
    client.login(username=user.username, password=password)
    return user


def make_worker_client(nodegroup):
    """Create a test client logged in as if it were `nodegroup`."""
    return OAuthAuthenticatedClient(
        get_worker_user(), token=nodegroup.api_token)


def explain_unexpected_response(expected_status, response):
    """Return human-readable failure message: unexpected http response."""
    return "Unexpected http status (expected %s): %s - %s" % (
        expected_status,
        response.status_code,
        response.content,
        )
