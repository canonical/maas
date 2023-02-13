# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for provisioningserver.rpc.boot_images"""


import os
from random import randint
from unittest.mock import ANY, sentinel
from urllib.parse import urlparse

from testtools.matchers import Equals, Is
from twisted.internet import defer
from twisted.internet.defer import inlineCallbacks, succeed
from twisted.internet.task import Clock

from maastesting import get_testing_timeout
from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith, MockNotCalled
from maastesting.testcase import MAASTestCase, MAASTwistedRunTest
from provisioningserver import concurrency
from provisioningserver.boot import tftppath
from provisioningserver.import_images import boot_resources
from provisioningserver.rpc import boot_images, clusterservice, region
from provisioningserver.rpc.boot_images import (
    _run_import,
    fix_sources_for_cluster,
    get_hosts_from_sources,
    import_boot_images,
    is_import_boot_images_running,
    list_boot_images,
    reload_boot_images,
)
from provisioningserver.rpc.region import UpdateLastImageSync
from provisioningserver.rpc.testing import MockLiveClusterToRegionRPCFixture
from provisioningserver.testing.config import (
    BootSourcesFixture,
    ClusterConfigurationFixture,
)
from provisioningserver.utils.twisted import pause

TIMEOUT = get_testing_timeout()


def make_sources():
    hosts = [factory.make_hostname().lower() for _ in range(2)]
    hosts.append(factory.make_ipv4_address())
    hosts.append("[%s]" % factory.make_ipv6_address())
    urls = [
        "http://%s:%s/images-stream/streams/v1/index.json"
        % (host, randint(1, 1000))
        for host in hosts
    ]
    sources = [{"url": url, "selections": []} for url in urls]
    return sources, hosts


class TestListBootImages(MAASTestCase):
    def setUp(self):
        super().setUp()
        self.tftp_root = self.make_dir()
        self.useFixture(ClusterConfigurationFixture(tftp_root=self.tftp_root))

    def test_calls_list_boot_images_with_boot_resource_storage(self):
        self.patch(boot_images, "CACHED_BOOT_IMAGES", None)
        mock_list_boot_images = self.patch(tftppath, "list_boot_images")
        list_boot_images()
        self.assertThat(
            mock_list_boot_images, MockCalledOnceWith(self.tftp_root)
        )

    def test_calls_list_boot_images_when_cache_is_None(self):
        self.patch(boot_images, "CACHED_BOOT_IMAGES", None)
        mock_list_boot_images = self.patch(tftppath, "list_boot_images")
        list_boot_images()
        self.assertThat(mock_list_boot_images, MockCalledOnceWith(ANY))

    def test_doesnt_call_list_boot_images_when_cache_is_not_None(self):
        fake_boot_images = [factory.make_name("image") for _ in range(3)]
        self.patch(boot_images, "CACHED_BOOT_IMAGES", fake_boot_images)
        mock_list_boot_images = self.patch(tftppath, "list_boot_images")
        self.expectThat(list_boot_images(), Equals(fake_boot_images))
        self.expectThat(mock_list_boot_images, MockNotCalled())


class TestReloadBootImages(MAASTestCase):
    def test_sets_CACHED_BOOT_IMAGES(self):
        self.patch(
            boot_images, "CACHED_BOOT_IMAGES", factory.make_name("old_cache")
        )
        fake_boot_images = [factory.make_name("image") for _ in range(3)]
        mock_list_boot_images = self.patch(tftppath, "list_boot_images")
        mock_list_boot_images.return_value = fake_boot_images
        reload_boot_images()
        self.assertEqual(boot_images.CACHED_BOOT_IMAGES, fake_boot_images)


class TestGetHostsFromSources(MAASTestCase):
    def test_returns_set_of_hosts_from_sources(self):
        sources, _ = make_sources()
        hosts = set()
        for source in sources:
            # Use the source to obtain the hosts and add it to a list.
            host = urlparse(source["url"]).hostname
            hosts.add(host)
            # If the host is an IPv6 address, add an extra fixed IPv6
            # with brackets.
            if ":" in host:
                hosts.add("[%s]" % host)
        self.assertCountEqual(hosts, get_hosts_from_sources(sources))


class TestFixSourcesForCluster(MAASTestCase):
    def test_removes_matching_path_from_maas_url_with_extra_slashes(self):
        sources = [{"url": "http://localhost/MAAS/images/index.json"}]
        observed = fix_sources_for_cluster(
            sources, "http://192.168.122.2/MAAS/////"
        )
        self.assertEqual(
            "http://192.168.122.2/MAAS/images/index.json", observed[0]["url"]
        )

    def test_removes_matching_path_from_maas_url(self):
        sources = [{"url": "http://localhost/MAAS/images/index.json"}]
        observed = fix_sources_for_cluster(
            sources, "http://192.168.122.2/MAAS/"
        )
        self.assertEqual(
            "http://192.168.122.2/MAAS/images/index.json", observed[0]["url"]
        )

    def test_removes_matching_path_with_extra_slashes_from_maas_url(self):
        sources = [{"url": "http://localhost///MAAS///images/index.json"}]
        observed = fix_sources_for_cluster(
            sources, "http://192.168.122.2/MAAS/"
        )
        self.assertEqual(
            "http://192.168.122.2/MAAS/images/index.json", observed[0]["url"]
        )

    def test_doesnt_remove_non_matching_path_from_maas_url(self):
        sources = [{"url": "http://localhost/MAAS/images/index.json"}]
        observed = fix_sources_for_cluster(
            sources, "http://192.168.122.2/not-matching/"
        )
        self.assertEqual(
            "http://192.168.122.2/not-matching/MAAS/images/index.json",
            observed[0]["url"],
        )

    def test_doesnt_remove_non_matching_path_from_maas_url_with_slashes(self):
        sources = [{"url": "http://localhost///MAAS/images/index.json"}]
        observed = fix_sources_for_cluster(
            sources, "http://192.168.122.2/not-matching////"
        )
        self.assertEqual(
            "http://192.168.122.2/not-matching/MAAS/images/index.json",
            observed[0]["url"],
        )


class TestRunImport(MAASTestCase):
    def make_archive_url(self, name=None):
        if name is None:
            name = factory.make_name("archive")
        return "http://{}.example.com/{}".format(
            name, factory.make_name("path")
        )

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

        return self.patch(boot_resources, "import_images", CaptureEnv())

    def test_run_import_integrates_with_boot_resources_function(self):
        # If the config specifies no sources, nothing will be imported.  But
        # the task succeeds without errors.
        fixture = self.useFixture(BootSourcesFixture([]))
        self.patch(boot_resources, "logger")
        self.patch(
            boot_resources, "locate_config"
        ).return_value = fixture.filename
        self.assertThat(
            _run_import(sources=[], maas_url=factory.make_simple_http_url()),
            Is(False),
        )

    def test_run_import_sets_GPGHOME(self):
        home = factory.make_name("home")
        self.patch(boot_images, "get_maas_user_gpghome").return_value = home
        fake = self.patch_boot_resources_function()
        _run_import(sources=[], maas_url=factory.make_simple_http_url())
        self.assertEqual(home, fake.env["GNUPGHOME"])

    def test_run_import_sets_proxy_if_given(self):
        proxy = "http://%s.example.com" % factory.make_name("proxy")
        fake = self.patch_boot_resources_function()
        _run_import(
            sources=[],
            maas_url=factory.make_simple_http_url(),
            http_proxy=proxy,
            https_proxy=proxy,
        )
        self.expectThat(fake.env["http_proxy"], Equals(proxy))
        self.expectThat(fake.env["https_proxy"], Equals(proxy))

    def test_run_import_sets_proxy_for_loopback(self):
        fake = self.patch_boot_resources_function()
        _run_import(sources=[], maas_url=factory.make_simple_http_url())
        self.assertEqual(
            fake.env["no_proxy"],
            (
                "localhost,::ffff:127.0.0.1,127.0.0.1,::1,"
                "[::ffff:127.0.0.1],[::1]"
            ),
        )

    def test_run_import_sets_proxy_for_source_host(self):
        host = factory.make_name("host").lower()
        maas_url = "http://%s/" % host
        sources, _ = make_sources()
        fake = self.patch_boot_resources_function()
        _run_import(sources=sources, maas_url=maas_url)
        self.assertCountEqual(
            fake.env["no_proxy"].split(","),
            [
                "localhost",
                "::ffff:127.0.0.1",
                "127.0.0.1",
                "::1",
                "[::ffff:127.0.0.1]",
                "[::1]",
            ]
            + [host],
        )

    def test_run_import_accepts_sources_parameter(self):
        fake = self.patch(boot_resources, "import_images")
        sources, _ = make_sources()
        _run_import(sources=sources, maas_url=factory.make_simple_http_url())
        self.assertThat(fake, MockCalledOnceWith(sources))

    def test_run_import_calls_reload_boot_images(self):
        fake_reload = self.patch(boot_images, "reload_boot_images")
        self.patch(boot_resources, "import_images")
        sources, _ = make_sources()
        _run_import(sources=sources, maas_url=factory.make_simple_http_url())
        self.assertThat(fake_reload, MockCalledOnceWith())


class TestImportBootImages(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    def setUp(self):
        super().setUp()
        self.patch(
            clusterservice, "get_all_interfaces_definition"
        ).return_value = {}

    @defer.inlineCallbacks
    def test_add_to_waiting_if_lock_already_held(self):
        yield concurrency.boot_images.acquire()
        deferToThread = self.patch(boot_images, "deferToThread")
        deferToThread.return_value = defer.succeed(None)
        maas_url = factory.make_simple_http_url()
        d = import_boot_images(sentinel.sources, maas_url)
        self.assertEqual(1, len(concurrency.boot_images.waiting))
        concurrency.boot_images.release()
        yield d
        self.assertThat(
            deferToThread,
            MockCalledOnceWith(
                _run_import,
                sentinel.sources,
                maas_url,
                http_proxy=None,
                https_proxy=None,
            ),
        )

    @defer.inlineCallbacks
    def test_never_more_than_one_waiting(self):
        yield concurrency.boot_images.acquire()
        deferToThread = self.patch(boot_images, "deferToThread")
        deferToThread.return_value = defer.succeed(None)
        maas_url = factory.make_simple_http_url()
        d = import_boot_images(sentinel.sources, maas_url)
        self.assertIsNone(import_boot_images(sentinel.sources, maas_url))
        self.assertEqual(1, len(concurrency.boot_images.waiting))
        concurrency.boot_images.release()
        yield d
        self.assertThat(
            deferToThread,
            MockCalledOnceWith(
                _run_import,
                sentinel.sources,
                maas_url,
                http_proxy=None,
                https_proxy=None,
            ),
        )

    def test_takes_lock_when_running(self):
        clock = Clock()
        deferToThread = self.patch(boot_images, "deferToThread")
        deferToThread.return_value = pause(1, clock)

        # Lock is acquired when import is started.
        import_boot_images(sentinel.sources, factory.make_simple_http_url())
        self.assertTrue(concurrency.boot_images.locked)

        # Lock is released once the download is done.
        clock.advance(1)
        self.assertFalse(concurrency.boot_images.locked)

    @inlineCallbacks
    def test_update_last_image_sync(self):
        get_maas_id = self.patch(boot_images.MAAS_ID, "get")
        get_maas_id.return_value = factory.make_string()
        getRegionClient = self.patch(boot_images, "getRegionClient")
        _run_import = self.patch_autospec(boot_images, "_run_import")
        _run_import.return_value = True
        maas_url = factory.make_simple_http_url()
        yield boot_images._import_boot_images(sentinel.sources, maas_url)
        _run_import.assert_called_once_with(
            sentinel.sources, maas_url, None, None
        )
        getRegionClient.assert_called_once()
        get_maas_id.assert_called_once()
        client = getRegionClient.return_value
        client.assert_called_once_with(
            UpdateLastImageSync, system_id=get_maas_id()
        )

    @inlineCallbacks
    def test_update_last_image_sync_always_updated(self):
        get_maas_id = self.patch(boot_images.MAAS_ID, "get")
        get_maas_id.return_value = factory.make_string()
        getRegionClient = self.patch(boot_images, "getRegionClient")
        _run_import = self.patch_autospec(boot_images, "_run_import")
        _run_import.return_value = False
        maas_url = factory.make_simple_http_url()
        yield boot_images._import_boot_images(sentinel.sources, maas_url)
        self.assertThat(
            _run_import,
            MockCalledOnceWith(sentinel.sources, maas_url, None, None),
        )
        self.assertThat(getRegionClient, MockCalledOnceWith())
        self.assertThat(get_maas_id, MockCalledOnceWith())
        client = getRegionClient.return_value
        self.assertThat(
            client,
            MockCalledOnceWith(UpdateLastImageSync, system_id=get_maas_id()),
        )

    @inlineCallbacks
    def test_update_last_image_sync_end_to_end(self):
        get_maas_id = self.patch(boot_images.MAAS_ID, "get")
        get_maas_id.return_value = factory.make_string()
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateLastImageSync
        )
        protocol.UpdateLastImageSync.return_value = succeed({})
        self.addCleanup((yield connecting))
        self.patch_autospec(boot_resources, "import_images")
        boot_resources.import_images.return_value = True
        sources, hosts = make_sources()
        maas_url = factory.make_simple_http_url()
        yield boot_images.import_boot_images(sources, maas_url)
        self.assertThat(
            boot_resources.import_images,
            MockCalledOnceWith(fix_sources_for_cluster(sources, maas_url)),
        )
        self.assertThat(
            protocol.UpdateLastImageSync,
            MockCalledOnceWith(protocol, system_id=get_maas_id()),
        )

    @inlineCallbacks
    def test_update_last_image_sync_end_to_end_import_not_performed(self):
        fixture = self.useFixture(MockLiveClusterToRegionRPCFixture())
        protocol, connecting = fixture.makeEventLoop(
            region.UpdateLastImageSync
        )
        protocol.UpdateLastImageSync.return_value = succeed({})
        self.addCleanup((yield connecting))
        self.patch_autospec(boot_resources, "import_images")
        boot_resources.import_images.return_value = False
        sources, hosts = make_sources()
        maas_url = factory.make_simple_http_url()
        yield boot_images.import_boot_images(sources, maas_url)
        self.assertThat(
            boot_resources.import_images,
            MockCalledOnceWith(fix_sources_for_cluster(sources, maas_url)),
        )
        self.assertThat(protocol.UpdateLastImageSync, MockNotCalled())


class TestIsImportBootImagesRunning(MAASTestCase):
    run_tests_with = MAASTwistedRunTest.make_factory(timeout=TIMEOUT)

    @defer.inlineCallbacks
    def test_returns_True_when_lock_is_held(self):
        yield concurrency.boot_images.acquire()
        self.addCleanup(concurrency.boot_images.release)
        self.assertTrue(is_import_boot_images_running())

    def test_returns_False_when_lock_is_not_held(self):
        self.assertFalse(is_import_boot_images_running())
