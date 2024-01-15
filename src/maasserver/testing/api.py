# Copyright 2013-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for API testing."""

__all__ = [
    "APITestCase",
    "APITransactionTestCase",
    "explain_unexpected_response",
    "make_worker_client",
]

import abc
import functools
import unittest

from django.contrib.auth.models import AnonymousUser
from testscenarios import multiply_scenarios

from maasserver.macaroon_auth import external_auth_enabled
from maasserver.models.user import create_auth_token
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.testing.testclient import MAASSensibleOAuthClient
from maasserver.utils.orm import transactional
from maasserver.worker_user import get_worker_user
from maastesting.testcase import MAASTestCase


def merge_scenarios(*scenario_lists):
    """Multiply `scenarios` together but ignoring empty or undefined ones."""
    scenario_lists = [
        scenarios
        for scenarios in scenario_lists
        if scenarios is not None and len(scenarios) != 0
    ]
    if len(scenario_lists) == 0:
        return None  # Ensure that testscenarios does not expand.
    elif len(scenario_lists) == 1:
        return scenario_lists[0]  # No need to multiply up.
    else:
        return multiply_scenarios(*scenario_lists)


class APITestType(abc.ABCMeta):
    """Base type for MAAS's Web API test cases."""

    @functools.lru_cache(maxsize=None)
    def forUsers(cls, **userfactories):
        """Create a new test class for the given users.

        :param users: A mapping from a descriptive name to a user factory.
        """
        name = "{}[for={}]".format(
            cls.__name__, ",".join(sorted(userfactories))
        )
        return type(name, (cls,), {"userfactories": userfactories})

    @property
    def ForAnonymous(cls):
        """API test for anonymous users only."""
        return cls.forUsers(anonymous=AnonymousUser)

    @property
    def ForAnonymousAndUser(cls):
        """API test for anonymous and normal users."""
        return cls.forUsers(anonymous=AnonymousUser, user=factory.make_User)

    @property
    def ForUser(cls):
        """API test for normal users only."""
        return cls.forUsers(user=factory.make_User)

    @property
    def ForUserAndAdmin(cls):
        """API test for normal and administrative users."""
        return cls.forUsers(user=factory.make_User, admin=factory.make_admin)

    @property
    def ForAdmin(cls):
        """API test for administrative users only."""
        return cls.forUsers(admin=factory.make_admin)

    @property
    def ForAnonymousAndUserAndAdmin(cls):
        """API test for anonymous, normal, and administrative users."""
        return cls.forUsers(
            anonymous=AnonymousUser,
            user=factory.make_User,
            admin=factory.make_admin,
        )


class APITestCaseBase(MAASTestCase, metaclass=APITestType):
    """Base class for logged-in API tests.

    This makes heavy use of scenarios to ensure that the Web API is tested
    using disparate clients and users.
    """

    # Django creates the client *before* calling setUp() so we make it as
    # close to a no-op here as we can before setting ourselves later. Sigh.
    # This test case class does not use the client_class for anything else.
    client_class = staticmethod(lambda: None)

    # The factories used to populate userfactory (via scenarios) in order to
    # test the API with different users. See `APITestType` for details of how
    # this is populated.
    userfactories = None

    # A no-arg callable that creates a user. This is set by scenarios to be
    # each factory from userfactories.
    userfactory = None

    # Populated in setUp() by a call to self.userfactory. Do not set this in a
    # subclass; it will be set for you.
    user = None

    # The factories used to populate clientfactory (via scenarios) in order to
    # test the API with different authentication mechanisms. Subclasses can
    # override this... but avoid _reducing_ this list; MAASAPIAuthentication
    # explicitly allows disparate authentication mechanisms.
    clientfactories = {"oauth": MAASSensibleOAuthClient}

    # A no-arg callable that creates a client. This is set by scenarios to be
    # each factory from clientfactories.
    clientfactory = None

    # Populated in setUp() by a call to self.clientfactory. Do not set this in
    # a subclass; it will be set for you.
    client = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Create scenarios for userfactories and clientfactories.
        scenarios_users = tuple(
            ("user=%s" % name, {"userfactory": self.userfactories[name]})
            for name in sorted(self.userfactories)
        )
        self.userfactories = ()
        scenarios_clients = tuple(
            ("client=%s" % name, {"clientfactory": self.clientfactories[name]})
            for name in sorted(self.clientfactories)
        )
        self.clientfactories = ()
        # Merge them into preexisting scenarios.
        self.scenarios = merge_scenarios(
            scenarios_users, scenarios_clients, self.scenarios
        )

    def setUp(self):
        if not callable(self.userfactory):
            raise AssertionError(
                "No user factory; set userfactory or userfactories, or "
                "inherit from a pre-canned subclass like ForUser."
            )
        if self.user is not None:
            raise AssertionError(
                "Do not set user; set userfactory or inherit from a "
                "pre-canned subclass like ForUser instead."
            )
        if not callable(self.clientfactory):
            raise AssertionError(
                "No client factory; set clientfactory or clientfactories."
            )
        if self.client is not None:
            raise AssertionError(
                "Do not set client; set clientfactory instead."
            )
        super().setUp()
        self.user = self.userfactory()
        self.client = self.clientfactory()
        self.client.login(user=self.user)

    def assertIsInstance(self, *args, **kwargs):
        return unittest.TestCase.assertIsInstance(self, *args, **kwargs)

    def assertSequenceEqual(self, *args, **kwargs):
        return unittest.TestCase.assertSequenceEqual(self, *args, **kwargs)

    def assertRaises(self, *args, **kwargs):
        return unittest.TestCase.assertRaises(self, *args, **kwargs)

    @transactional
    def become_admin(self):
        """Promote `self.user` to admin."""
        self.assertFalse(
            self.user.is_anonymous, "Cannot promote anonymous user to admin."
        )
        if external_auth_enabled():
            # if external auth is enabled, mark the user as remote, otherwise
            # he wouldn't be able to authenticate
            self.user.userprofile.is_local = False
            self.user.userprofile.save()
        self.user.is_superuser = True
        self.user.save()

    @transactional
    def become_non_local(self):
        """Promote `self.user` to non local."""
        if external_auth_enabled():
            # if external auth is enabled, mark the user as remote, otherwise
            # he wouldn't be able to authenticate
            self.user.userprofile.is_local = False
            self.user.userprofile.save()
        else:
            raise ValueError("Not using external authentication or RBAC.")


class APITestCase(APITestCaseBase, MAASServerTestCase):
    """Class for logged-in API tests within a single transaction."""


class APITransactionTestCase(APITestCaseBase, MAASTransactionServerTestCase):
    """Class for logged-in API tests with the ability to use transactions."""


def make_worker_client(rack_controller):
    """Create a test client logged in as if it were `rack_controller`."""
    assert (
        get_worker_user() == rack_controller.owner
    ), "Rack controller owner should be the MAAS worker user."
    token = create_auth_token(rack_controller.owner)
    return MAASSensibleOAuthClient(rack_controller.owner, token=token)


def explain_unexpected_response(expected_status, response):
    """Return human-readable failure message: unexpected http response."""
    return "Unexpected http status (expected {}): {} - {}".format(
        expected_status,
        response.status_code,
        response.content,
    )
