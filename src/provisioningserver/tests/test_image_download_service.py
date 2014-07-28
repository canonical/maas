# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for src/provisioningserver/image_download_service.py"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from datetime import timedelta
import os

from maastesting.factory import factory
from maastesting.matchers import (
    get_mock_calls,
    MockCalledOnceWith,
    MockNotCalled,
    )
from mock import (
    Mock,
    sentinel,
    )
from provisioningserver import (
    image_download_service,
    utils,
    )
from provisioningserver.image_download_service import (
    import_boot_images,
    PeriodicImageDownloadService,
    service_lock,
    )
from provisioningserver.import_images import boot_resources
from provisioningserver.rpc.exceptions import NoConnectionsAvailable
from provisioningserver.testing.config import BootSourcesFixture
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver.utils import pause
from testtools.deferredruntest import AsynchronousDeferredRunTest
from twisted.application.internet import TimerService
from twisted.internet import defer
from twisted.internet.task import Clock


class TestPeriodicImageDownloadService(PservTestCase):

    run_tests_with = AsynchronousDeferredRunTest.make_factory(timeout=5)

    def test_init(self):
        service = PeriodicImageDownloadService(
            sentinel.service, sentinel.clock, sentinel.uuid)
        self.assertIsInstance(service, TimerService)
        self.assertIs(service.clock, sentinel.clock)
        self.assertIs(service.uuid, sentinel.uuid)
        self.assertIs(service.client_service, sentinel.service)

    def patch_download(self, service, return_value):
        patched = self.patch(service, '_start_download')
        patched.return_value = defer.succeed(return_value)
        return patched

    def test_is_called_every_interval(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        # Avoid actual downloads:
        self.patch_download(service, None)
        maas_meta_last_modified = self.patch(
            image_download_service, 'maas_meta_last_modified')
        maas_meta_last_modified.return_value = None
        service.startService()

        # The first call is issued at startup.
        self.assertEqual(1, len(get_mock_calls(maas_meta_last_modified)))

        # Wind clock forward one second less than the desired interval.
        clock.advance(service.check_interval - 1)
        # No more periodic calls made.
        self.assertEqual(1, len(get_mock_calls(maas_meta_last_modified)))

        # Wind clock forward one second, past the interval.
        clock.advance(1)

        # Now there were two calls.
        self.assertEqual(2, len(get_mock_calls(maas_meta_last_modified)))

        # Forward another interval, should be three calls.
        clock.advance(service.check_interval)
        self.assertEqual(3, len(get_mock_calls(maas_meta_last_modified)))

    def test_no_download_if_no_meta_file(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        _start_download = self.patch_download(service, None)
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = None
        service.startService()
        self.assertThat(_start_download, MockNotCalled())

    def test_initiates_download_if_one_week_has_passed(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        _start_download = self.patch_download(service, None)
        one_week_ago = clock.seconds() - timedelta(weeks=1).total_seconds()
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = one_week_ago
        service.startService()
        self.assertThat(_start_download, MockCalledOnceWith())

    def test_no_download_if_one_week_has_not_passed(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.service, clock, sentinel.uuid)
        _start_download = self.patch_download(service, None)
        one_week = timedelta(weeks=1).total_seconds()
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = clock.seconds()
        clock.advance(one_week - 1)
        service.startService()
        self.assertThat(_start_download, MockNotCalled())

    def test_download_is_initiated_in_new_thread(self):
        clock = Clock()
        maas_meta_last_modified = self.patch(
            image_download_service, 'maas_meta_last_modified')
        one_week = timedelta(weeks=1).total_seconds()
        maas_meta_last_modified.return_value = clock.seconds() - one_week
        rpc_client = Mock()
        client_call = Mock()
        client_call.side_effect = [
            defer.succeed(dict(sources=sentinel.sources)),
            defer.succeed(dict(
                http_proxy=sentinel.http_proxy,
                https_proxy=sentinel.https_proxy)),
            ]
        rpc_client.getClient.return_value = client_call

        # We could patch out 'import_boot_images' instead here but I
        # don't do that for 2 reasons:
        # 1. It requires spinning the reactor again before being able to
        # test the result.
        # 2. It means there's no thread to clean up after the test.
        deferToThread = self.patch(image_download_service, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        service = PeriodicImageDownloadService(
            rpc_client, clock, sentinel.uuid)
        service.startService()
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                import_boot_images, sentinel.sources, sentinel.http_proxy,
                sentinel.https_proxy))

    def test_no_download_if_no_rpc_connections(self):
        rpc_client = Mock()
        failure = NoConnectionsAvailable()
        rpc_client.getClient.return_value.side_effect = failure

        deferToThread = self.patch(image_download_service, 'deferToThread')
        service = PeriodicImageDownloadService(
            rpc_client, Clock(), sentinel.uuid)
        service.startService()
        self.assertThat(deferToThread, MockNotCalled())

    @defer.inlineCallbacks
    def test_does_not_run_if_lock_taken(self):
        maas_meta_last_modified = self.patch(
            image_download_service, 'maas_meta_last_modified')
        yield service_lock.acquire()
        self.addCleanup(service_lock.release)
        service = PeriodicImageDownloadService(
            sentinel.rpc, Clock(), sentinel.uuid)
        service.startService()
        self.assertThat(maas_meta_last_modified, MockNotCalled())

    def test_takes_lock_when_running(self):
        clock = Clock()
        service = PeriodicImageDownloadService(
            sentinel.rpc, clock, sentinel.uuid)

        # Patch the download func so it's just a Deferred that waits for
        # one second.
        _start_download = self.patch(service, '_start_download')
        _start_download.return_value = pause(1, clock)

        # Set conditions for a required download:
        one_week_ago = clock.seconds() - timedelta(weeks=1).total_seconds()
        self.patch(
            image_download_service,
            'maas_meta_last_modified').return_value = one_week_ago

        # Lock is acquired for the first download after startup.
        service.startService()
        self.assertTrue(service_lock.locked)

        # Lock is released once the download is done.
        clock.advance(1)
        self.assertFalse(service_lock.locked)


class TestImportBootImages(PservTestCase):

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

    def test_import_boot_images_integrates_with_boot_resources_function(self):
        # If the config specifies no sources, nothing will be imported.  But
        # the task succeeds without errors.
        fixture = self.useFixture(BootSourcesFixture([]))
        self.patch(boot_resources, 'logger')
        self.patch(boot_resources, 'locate_config').return_value = (
            fixture.filename)
        self.assertIsNone(import_boot_images(sources=[]))

    def test_import_boot_images_sets_GPGHOME(self):
        home = factory.make_name('home')
        self.patch(image_download_service, 'MAAS_USER_GPGHOME', home)
        fake = self.patch_boot_resources_function()
        import_boot_images(sources=[])
        self.assertEqual(home, fake.env['GNUPGHOME'])

    def test_import_boot_images_sets_proxy_if_given(self):
        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        proxy_vars = ['http_proxy', 'https_proxy']
        fake = self.patch_boot_resources_function()
        import_boot_images(sources=[], http_proxy=proxy, https_proxy=proxy)
        self.assertEqual(
            {
                var: proxy
                for var in proxy_vars
            }, utils.filter_dict(fake.env, proxy_vars))

    def test_import_boot_images_leaves_proxy_unchanged_if_not_given(self):
        proxy_vars = ['http_proxy', 'https_proxy']
        fake = self.patch_boot_resources_function()
        import_boot_images(sources=[])
        self.assertEqual({}, utils.filter_dict(fake.env, proxy_vars))

    def test_import_boot_images_accepts_sources_parameter(self):
        fake = self.patch(boot_resources, 'import_images')
        sources = [
            {
                'path': "http://example.com",
                'selections': [
                    {
                        'release': "trusty",
                        'arches': ["amd64"],
                        'subarches': ["generic"],
                        'labels': ["release"]
                    },
                ],
            },
        ]
        import_boot_images(sources=sources)
        self.assertThat(fake, MockCalledOnceWith(sources))
