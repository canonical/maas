# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.testing`."""

from __future__ import (
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver import provisioning
from maasserver.testing import TestCase
from provisioningserver.testing import fakeapi


class TestTestCase(TestCase):
    """Tests for `TestCase`."""

    def test_patched_in_fake_papi(self):
        # TestCase.setUp() patches in a fake provisioning API so that we can
        # observe what the signal handlers are doing.
        papi_fake = provisioning.get_provisioning_api_proxy()
        self.assertIsInstance(
            papi_fake, fakeapi.FakeSynchronousProvisioningAPI)
        # The fake has some limited, automatically generated, sample
        # data. This is required for many tests to run. First there is a
        # sample distro.
        self.assertEqual(1, len(papi_fake.distros))
        [distro_name] = papi_fake.distros
        expected_distros = {
            distro_name: {
                u'initrd': u'initrd',
                u'kernel': u'kernel',
                u'name': distro_name,
                },
            }
        self.assertEqual(expected_distros, papi_fake.distros)
        # Second there is a sample profile, referring to the distro.
        self.assertEqual(1, len(papi_fake.profiles))
        [profile_name] = papi_fake.profiles
        expected_profiles = {
            profile_name: {
                u'distro': distro_name,
                u'name': profile_name,
                },
            }
        self.assertEqual(expected_profiles, papi_fake.profiles)
        # There are no nodes.
        self.assertEqual({}, papi_fake.nodes)
