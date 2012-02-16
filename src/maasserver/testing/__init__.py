# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    print_function,
    unicode_literals,
    )

"""Tests for `maasserver`."""

__metaclass__ = type
__all__ = [
    "get_fake_provisioning_api_proxy",
    "LoggedInTestCase",
    "TestCase",
    ]

from uuid import uuid1

from fixtures import MonkeyPatch
from maasserver.testing.factory import factory
import maastesting
from provisioningserver.testing import fakeapi


def get_fake_provisioning_api_proxy():
    papi_fake = fakeapi.FakeSynchronousProvisioningAPI()
    distro = papi_fake.add_distro(
        "distro-%s" % uuid1().get_hex(),
        "initrd", "kernel")
    papi_fake.add_profile(
        "profile-%s" % uuid1().get_hex(),
        distro)
    return papi_fake


class TestCase(maastesting.TestCase):

    def setUp(self):
        super(TestCase, self).setUp()
        papi_fake = get_fake_provisioning_api_proxy()
        papi_fake_fixture = MonkeyPatch(
            "maasserver.provisioning.get_provisioning_api_proxy",
            lambda: papi_fake)
        self.useFixture(papi_fake_fixture)


class LoggedInTestCase(TestCase):

    def setUp(self):
        super(LoggedInTestCase, self).setUp()
        self.logged_in_user = factory.make_user(password='test')
        self.client.login(
            username=self.logged_in_user.username, password='test')
