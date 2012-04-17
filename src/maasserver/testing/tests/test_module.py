# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `maasserver.testing`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = []

from maasserver import provisioning
from maasserver.testing import (
    reload_object,
    reload_objects,
    )
from maasserver.testing.models import TestModel
from maasserver.testing.testcase import (
    TestCase,
    TestModelTestCase,
    )
from provisioningserver.testing import fakeapi

# Horrible kludge.  Works around a bug where delete() does not work on
# test models when using nose.  Without this, running the tests in this
# module fails at the delete() calls, saying a table node_c does not
# exist.  (Running just the test case passes, but running the entire
# module's tests fails even if the failing test case is the only one).
#
# https://github.com/jbalogh/django-nose/issues/15
TestModel._meta.get_all_related_objects()


class TestTestCase(TestCase):
    """Tests for `TestCase`."""

    def test_patched_in_fake_papi(self):
        # TestCase.setUp() patches in a fake provisioning API so that we can
        # observe what the signal handlers are doing.
        papi_fake = provisioning.get_provisioning_api_proxy()
        self.assertIsInstance(papi_fake, provisioning.ProvisioningProxy)
        self.assertIsInstance(
            papi_fake.proxy, fakeapi.FakeSynchronousProvisioningAPI)
        # The fake has some limited, automatically generated, sample
        # data. This is required for many tests to run. First there is a
        # sample distro.
        self.assertEqual(1, len(papi_fake.distros))
        [distro_name] = papi_fake.distros
        expected_distros = {
            distro_name: {
                'initrd': 'initrd',
                'kernel': 'kernel',
                'name': distro_name,
                },
            }
        self.assertEqual(expected_distros, papi_fake.distros)
        # Second there is a sample profile, referring to the distro.
        self.assertEqual(1, len(papi_fake.profiles))
        [profile_name] = papi_fake.profiles
        expected_profiles = {
            profile_name: {
                'distro': distro_name,
                'name': profile_name,
                },
            }
        self.assertEqual(expected_profiles, papi_fake.profiles)
        # There are no nodes.
        self.assertEqual({}, papi_fake.nodes)


class TestHelpers(TestModelTestCase):
    """Test helper functions."""

    app = 'maasserver.testing'

    def test_reload_object_reloads_object(self):
        test_obj = TestModel(text="old text")
        test_obj.save()
        TestModel.objects.filter(id=test_obj.id).update(text="new text")
        self.assertEqual("new text", reload_object(test_obj).text)

    def test_reload_object_returns_None_for_deleted_object(self):
        test_obj = TestModel()
        test_obj.save()
        TestModel.objects.filter(id=test_obj.id).delete()
        self.assertIsNone(reload_object(test_obj))

    def test_reload_objects_reloads_objects(self):
        texts = ['1 text', '2 text', '3 text']
        objs = [TestModel(text=text) for text in texts]
        for obj in objs:
            obj.save()
        texts[0] = "different text"
        TestModel.objects.filter(id=objs[0].id).update(text=texts[0])
        self.assertItemsEqual(
            texts, [obj.text for obj in reload_objects(TestModel, objs)])

    def test_reload_objects_omits_deleted_objects(self):
        objs = [TestModel() for counter in range(3)]
        for obj in objs:
            obj.save()
        dead_obj = objs.pop(0)
        TestModel.objects.filter(id=dead_obj.id).delete()
        self.assertItemsEqual(objs, reload_objects(TestModel, objs))
