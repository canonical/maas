# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioningserver.rpc.boot_images"""

__all__ = []

import os
from random import randint

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
)
from maastesting.testcase import MAASTwistedRunTest
from mock import (
    ANY,
    sentinel,
)
from provisioningserver import concurrency
from provisioningserver.boot import tftppath
from provisioningserver.import_images import boot_resources
from provisioningserver.rpc import boot_images
from provisioningserver.rpc.boot_images import (
    _run_import,
    fix_sources_for_cluster,
    get_hosts_from_sources,
    import_boot_images,
    is_import_boot_images_running,
    list_boot_images,
    reload_boot_images,
)
from provisioningserver.testing.config import (
    BootSourcesFixture,
    ClusterConfigurationFixture,
)
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver.utils.twisted import pause
from testtools.matchers import Equals
from twisted.internet import defer
from twisted.internet.task import Clock


def make_sources():
    hosts = [factory.make_name('host').lower() for _ in range(3)]
    urls = [
        'http://%s:%s/images-stream/streams/v1/index.json' % (
            host, randint(1, 1000))
        for host in hosts
        ]
    sources = [
        {'url': url, 'selections': []}
        for url in urls
        ]
    return sources, hosts


class TestListBootImages(PservTestCase):

    def setUp(self):
        super(TestListBootImages, self).setUp()
        self.tftp_root = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=self.tftp_root))

    def test__calls_list_boot_images_with_boot_resource_storage(self):
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
        mock_list_boot_images = self.patch(tftppath, 'list_boot_images')
        list_boot_images()
        self.assertThat(
            mock_list_boot_images,
            MockCalledOnceWith(self.tftp_root))

    def test__calls_list_boot_images_when_cache_is_None(self):
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', None)
        mock_list_boot_images = self.patch(tftppath, 'list_boot_images')
        list_boot_images()
        self.assertThat(
            mock_list_boot_images,
            MockCalledOnceWith(ANY))

    def test__doesnt_call_list_boot_images_when_cache_is_not_None(self):
        fake_boot_images = [factory.make_name('image') for _ in range(3)]
        self.patch(boot_images, 'CACHED_BOOT_IMAGES', fake_boot_images)
        mock_list_boot_images = self.patch(tftppath, 'list_boot_images')
        self.expectThat(list_boot_images(), Equals(fake_boot_images))
        self.expectThat(
            mock_list_boot_images,
            MockNotCalled())


class TestReloadBootImages(PservTestCase):

    def test__sets_CACHED_BOOT_IMAGES(self):
        self.patch(
            boot_images, 'CACHED_BOOT_IMAGES', factory.make_name('old_cache'))
        fake_boot_images = [factory.make_name('image') for _ in range(3)]
        mock_list_boot_images = self.patch(tftppath, 'list_boot_images')
        mock_list_boot_images.return_value = fake_boot_images
        reload_boot_images()
        self.assertEqual(
            boot_images.CACHED_BOOT_IMAGES, fake_boot_images)


class TestGetHostsFromSources(PservTestCase):

    def test__returns_set_of_hosts_from_sources(self):
        sources, hosts = make_sources()
        self.assertItemsEqual(hosts, get_hosts_from_sources(sources))


class TestFixSourcesForCluster(PservTestCase):

    def set_maas_url(self, url):
        self.useFixture(ClusterConfigurationFixture(maas_url=url))

    def test__removes_matching_path_from_maas_url_with_extra_slashes(self):
        self.set_maas_url("http://192.168.122.2/MAAS/////")
        sources = [
            {
                "url": "http://localhost/MAAS/images/index.json"
            }
        ]
        observered = fix_sources_for_cluster(sources)
        self.assertEqual(
            "http://192.168.122.2/MAAS/images/index.json",
            observered[0]['url'])

    def test__removes_matching_path_from_maas_url(self):
        self.set_maas_url("http://192.168.122.2/MAAS/")
        sources = [
            {
                "url": "http://localhost/MAAS/images/index.json"
            }
        ]
        observered = fix_sources_for_cluster(sources)
        self.assertEqual(
            "http://192.168.122.2/MAAS/images/index.json",
            observered[0]['url'])

    def test__removes_matching_path_with_extra_slashes_from_maas_url(self):
        self.set_maas_url("http://192.168.122.2/MAAS/")
        sources = [
            {
                "url": "http://localhost///MAAS///images/index.json"
            }
        ]
        observered = fix_sources_for_cluster(sources)
        self.assertEqual(
            "http://192.168.122.2/MAAS/images/index.json",
            observered[0]['url'])

    def test__doesnt_remove_non_matching_path_from_maas_url(self):
        self.set_maas_url("http://192.168.122.2/not-matching/")
        sources = [
            {
                "url": "http://localhost/MAAS/images/index.json"
            }
        ]
        observered = fix_sources_for_cluster(sources)
        self.assertEqual(
            "http://192.168.122.2/not-matching/MAAS/images/index.json",
            observered[0]['url'])

    def test__doesnt_remove_non_matching_path_from_maas_url_with_slashes(self):
        self.set_maas_url("http://192.168.122.2/not-matching////")
        sources = [
            {
                "url": "http://localhost///MAAS/images/index.json"
            }
        ]
        observered = fix_sources_for_cluster(sources)
        self.assertEqual(
            "http://192.168.122.2/not-matching/MAAS/images/index.json",
            observered[0]['url'])


class TestRunImport(PservTestCase):

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

    def test__run_import_sets_proxy_if_given(self):
        proxy = 'http://%s.example.com' % factory.make_name('proxy')
        fake = self.patch_boot_resources_function()
        _run_import(sources=[], http_proxy=proxy, https_proxy=proxy)
        self.expectThat(fake.env['http_proxy'], Equals(proxy))
        self.expectThat(fake.env['https_proxy'], Equals(proxy))

    def test__run_import_sets_proxy_for_loopback(self):
        fake = self.patch_boot_resources_function()
        _run_import(sources=[])
        self.assertEqual(fake.env['no_proxy'], "localhost,127.0.0.1,::1")

    def test__run_import_sets_proxy_for_source_host(self):
        host = factory.make_name("host").lower()
        maas_url = "http://%s/" % host
        self.useFixture(ClusterConfigurationFixture(maas_url=maas_url))
        sources, _ = make_sources()
        fake = self.patch_boot_resources_function()
        _run_import(sources=sources)
        self.assertItemsEqual(
            fake.env['no_proxy'].split(','),
            ["localhost", "127.0.0.1", "::1"] + [host])

    def test__run_import_accepts_sources_parameter(self):
        fake = self.patch(boot_resources, 'import_images')
        sources, _ = make_sources()
        _run_import(sources=sources)
        self.assertThat(fake, MockCalledOnceWith(sources))

    def test__run_import_calls_reload_boot_images(self):
        fake_reload = self.patch(boot_images, 'reload_boot_images')
        self.patch(boot_resources, 'import_images')
        sources, _ = make_sources()
        _run_import(sources=sources)
        self.assertThat(fake_reload, MockCalledOnceWith())


class TestImportBootImages(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @defer.inlineCallbacks
    def test__does_not_run_if_lock_taken(self):
        yield concurrency.boot_images.acquire()
        self.addCleanup(concurrency.boot_images.release)
        deferToThread = self.patch(boot_images, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        yield import_boot_images(sentinel.sources)
        self.assertThat(
            deferToThread, MockNotCalled())

    @defer.inlineCallbacks
    def test__calls__run_import_using_deferToThread(self):
        deferToThread = self.patch(boot_images, 'deferToThread')
        deferToThread.return_value = defer.succeed(None)
        yield import_boot_images(sentinel.sources)
        self.assertThat(
            deferToThread, MockCalledOnceWith(
                _run_import, sentinel.sources,
                http_proxy=None, https_proxy=None))

    def test__takes_lock_when_running(self):
        clock = Clock()
        deferToThread = self.patch(boot_images, 'deferToThread')
        deferToThread.return_value = pause(1, clock)

        # Lock is acquired when import is started.
        import_boot_images(sentinel.sources)
        self.assertTrue(concurrency.boot_images.locked)

        # Lock is released once the download is done.
        clock.advance(1)
        self.assertFalse(concurrency.boot_images.locked)


class TestIsImportBootImagesRunning(PservTestCase):

    run_tests_with = MAASTwistedRunTest.make_factory(timeout=5)

    @defer.inlineCallbacks
    def test__returns_True_when_lock_is_held(self):
        yield concurrency.boot_images.acquire()
        self.addCleanup(concurrency.boot_images.release)
        self.assertTrue(is_import_boot_images_running())

    def test__returns_False_when_lock_is_not_held(self):
        self.assertFalse(is_import_boot_images_running())
