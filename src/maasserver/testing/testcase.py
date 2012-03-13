# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Custom test-case classes."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'LoggedInTestCase',
    'TestCase',
    'TestModelTestCase',
    ]

from fixtures import MonkeyPatch
from maasserver.testing import get_fake_provisioning_api_proxy
from maasserver.testing.factory import factory
import maastesting.testcase


class TestCase(maastesting.testcase.TestCase):

    def setUp(self):
        super(TestCase, self).setUp()
        papi_fake = get_fake_provisioning_api_proxy()
        papi_fake_fixture = MonkeyPatch(
            "maasserver.provisioning.get_provisioning_api_proxy",
            lambda: papi_fake)
        self.useFixture(papi_fake_fixture)


class TestModelTestCase(TestCase, maastesting.testcase.TestModelTestCase):
    pass


class LoggedInTestCase(TestCase):

    def setUp(self):
        super(LoggedInTestCase, self).setUp()
        self.logged_in_user = factory.make_user(password='test')
        self.client.login(
            username=self.logged_in_user.username, password='test')
