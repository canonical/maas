# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test the start up utility."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from maasserver import (
    eventloop,
    locks,
    start_up,
    )
from maasserver.bootresources import ensure_boot_source_definition
from maasserver.clusterrpc.testing.boot_images import make_rpc_boot_image
from maasserver.models import (
    BootSource,
    BootSourceSelection,
    NodeGroup,
    )
from maasserver.testing.eventloop import RegionEventLoopFixture
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.fakemethod import FakeMethod
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from testtools.matchers import (
    Equals,
    HasLength,
    )


class LockChecker:
    """Callable.  Records calls, and whether the startup lock was held."""

    def __init__(self, lock_file=None):
        self.call_count = 0
        self.lock_was_held = None

    def __call__(self):
        self.call_count += 1
        self.lock_was_held = locks.startup.is_locked()


class TestStartUp(MAASServerTestCase):
    """Tests for the `start_up` function.

    The actual work happens in `inner_start_up` and `test_start_up`; the tests
    you see here are for the locking wrapper only.
    """

    def setUp(self):
        super(TestStartUp, self).setUp()
        self.useFixture(RegionEventLoopFixture())
        self.patch(start_up, 'create_gnupg_home')
        self.patch(start_up, 'import_resources')

    def tearDown(self):
        super(TestStartUp, self).tearDown()
        # start_up starts the Twisted event loop, so we need to stop it.
        eventloop.reset().wait(5)

    def test_start_up_runs_in_exclusion(self):
        lock_checker = LockChecker()
        self.patch(start_up, 'inner_start_up', lock_checker)
        start_up.start_up()
        self.assertEqual(1, lock_checker.call_count)
        self.assertEqual(True, lock_checker.lock_was_held)


class TestStartImportOnUpgrade(MAASServerTestCase):
    """Tests for the `start_import_on_upgrade` function."""

    def setUp(self):
        super(TestStartImportOnUpgrade, self).setUp()
        ensure_boot_source_definition()
        self.mock_import_resources = self.patch(start_up, 'import_resources')

    def test__does_nothing_if_boot_resources_exist(self):
        mock_list_boot_images = self.patch(start_up, 'list_boot_images')
        factory.make_BootResource()
        start_up.start_import_on_upgrade()
        self.assertThat(mock_list_boot_images, MockNotCalled())

    def test__does_nothing_if_list_boot_images_is_empty(self):
        self.patch(start_up, 'list_boot_images').return_value = []
        start_up.start_import_on_upgrade()
        self.assertThat(self.mock_import_resources, MockNotCalled())

    def test__calls_import_resources(self):
        self.patch(start_up, 'list_boot_images').return_value = [
            make_rpc_boot_image(),
            ]
        start_up.start_import_on_upgrade()
        self.assertThat(self.mock_import_resources, MockCalledOnceWith())

    def test__sets_source_selections_based_on_boot_images(self):
        boot_images = [
            make_rpc_boot_image()
            for _ in range(3)
            ]
        self.patch(start_up, 'list_boot_images').return_value = boot_images
        start_up.start_import_on_upgrade()

        boot_source = BootSource.objects.first()
        for image in boot_images:
            selection = BootSourceSelection.objects.get(
                boot_source=boot_source, os=image["osystem"],
                release=image["release"])
            self.assertIsNotNone(selection)
            self.expectThat(selection.arches, Equals([image["architecture"]]))
            self.expectThat(selection.subarches, Equals(["*"]))
            self.expectThat(selection.labels, Equals([image["label"]]))


class TestInnerStartUp(MAASServerTestCase):
    """Tests for the actual work done in `inner_start_up`."""

    def setUp(self):
        super(TestInnerStartUp, self).setUp()
        self.patch(start_up, 'import_resources')
        self.mock_create_gnupg_home = self.patch(
            start_up, 'create_gnupg_home')

    def test__calls_write_full_dns_config(self):
        recorder = FakeMethod()
        self.patch(start_up, 'write_full_dns_config', recorder)
        start_up.inner_start_up()
        self.assertEqual(
            (1, [()]),
            (recorder.call_count, recorder.extract_args()))

    def test__creates_master_nodegroup(self):
        start_up.inner_start_up()
        clusters = NodeGroup.objects.all()
        self.assertThat(clusters, HasLength(1))
        self.assertItemsEqual([NodeGroup.objects.ensure_master()], clusters)

    def test__calls_create_gnupg_home(self):
        start_up.inner_start_up()
        self.assertThat(self.mock_create_gnupg_home, MockCalledOnceWith())

    def test__initialises_boot_source_config(self):
        self.assertItemsEqual([], BootSource.objects.all())
        start_up.inner_start_up()
        self.assertThat(BootSource.objects.all(), HasLength(1))

    def test__calls_start_import_on_upgrade(self):
        mock_start_import = self.patch(start_up, 'start_import_on_upgrade')
        start_up.inner_start_up()
        self.expectThat(mock_start_import, MockCalledOnceWith())
