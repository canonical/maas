# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioningserver.rpc.boot_images"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTwistedRunTest
from mock import sentinel
from provisioningserver.boot import tftppath
from provisioningserver.config import Config
from provisioningserver.import_images import boot_resources
from provisioningserver.rpc import boot_images
from provisioningserver.rpc.boot_images import (
    _run_import,
    import_boot_images,
    list_boot_images,
    )
from provisioningserver.testing.config import BootSourcesFixture
from provisioningserver.testing.testcase import PservTestCase
from twisted.internet import defer


class TestListBootImages(PservTestCase):

    def test__calls_list_boot_images_with_resource_root(self):
        self.patch(Config, 'load_from_cache').return_value = {
            'tftp': {
                'resource_root': sentinel.resource_root,
                }
            }
        mock_list_boot_images = self.patch(tftppath, 'list_boot_images')
        list_boot_images()
        self.assertThat(
            mock_list_boot_images,
            MockCalledOnceWith(sentinel.resource_root))


class TestRunImport(PservTestCase):

    # Cargo-culted from src/provisioningserver/tests/test_tasks.py
    # At some point the celery task will go away and the previous code can
    # simply be deleted.

    def make_archive_url(self, name=None):
        if name is None:
            name = factory.make_name('archive')
        return 'http://%s.example.com/%s' % (name, factory.make_name('path'))

    def patch_boot_resources_function(self):
        """Patch out `boot_resources.import_images`.

        Returns the installed fake.  After the fake has been called, but not
        before, its `env` attribute will have a copy of the environment dict.
        """

        class CaptureEnv:
            """Fake function; records a copy of the environment."""

            def __call__(self, *args, **kwargs):
                self.args = args
                self.env = os.environ.copy()

        return self.patch(boot_resources, 'import_images', CaptureEnv())

    def test__run_import_integrates_with_boot_resources_function(self):
        # If the config specifies no sources, nothing will be imported.  But
        # the task succeeds without errors.
        fixture = self.useFixture(BootSourcesFixture([]))
        self.patch(boot_resources, 'logger')
        self.patch(boot_resources, 'locate_config').return_value = (
            fixture.filename)
        self.assertIsNone(_run_import(sources=[]))

    def test__run_import_sets_GPGHOME(self):
        home = factory.make_name('home')
        self.patch(boot_images, 'get_maas_user_gpghome').return_value = home
        fake = self.patch_boot_resources_function()
        _run_import(sources=[])
        self.assertEqual(home, fake.env['GNUPGHOME'])

    def test__run_import_accepts_sources_parameter(self):
        fake = self.patch(boot_resources, 'import_images')
        sources = [
            {
                'path': "http://example.com",
                'selections': [
                    {
                        'os': "ubuntu",
                        'release': "trusty",
                        'arches': ["amd64"],
                        'subarches': ["generic"],
                        'labels': ["release"]
                    },
                ],
            },
        ]
        _run_import(sources=sources)
        self.assertThat(fake, MockCalledOnceWith(sources))


class TestImportBootImages(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @defer.inlineCallbacks
    def test__calls__run_import_using_deferToThread(self):
        deferToThread = self.patch(boot_images, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        yield import_boot_images(sentinel.sources)
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                _run_import, sentinel.sources))
