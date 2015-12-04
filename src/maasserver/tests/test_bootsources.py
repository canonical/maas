# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.bootsources."""

__all__ = []

from os import environ

from maasserver import bootsources
from maasserver.bootsources import (
    cache_boot_sources,
    ensure_boot_source_definition,
    get_boot_sources,
    get_os_info_from_boot_sources,
)
from maasserver.components import (
    get_persistent_error,
    register_persistent_error,
)
from maasserver.enum import COMPONENT
from maasserver.models import (
    BootSource,
    BootSourceCache,
    BootSourceSelection,
    Config,
)
from maasserver.models.testing import UpdateBootSourceCacheDisconnected
from maasserver.testing.factory import factory
from maasserver.testing.testcase import (
    MAASServerTestCase,
    MAASTransactionServerTestCase,
)
from maasserver.tests.test_bootresources import SimplestreamsEnvFixture
from mock import MagicMock
from provisioningserver.import_images import (
    download_descriptions as download_descriptions_module,
)
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
)
from provisioningserver.import_images.helpers import ImageSpec
from requests.exceptions import ConnectionError
from testtools.matchers import HasLength


def patch_and_capture_env_for_download_all_image_descriptions(testcase):
    class CaptureEnv:
        """Fake function; records a copy of the environment."""

        def __call__(self, *args, **kwargs):
            self.args = args
            self.env = environ.copy()
            return MagicMock()

    capture = testcase.patch(
        bootsources, 'download_all_image_descriptions', CaptureEnv())
    return capture


def make_image_spec(
        os=None, arch=None, subarch=None, release=None, label=None):
    if os is None:
        os = factory.make_name('os')
    if arch is None:
        arch = factory.make_name('arch')
    if subarch is None:
        subarch = factory.make_name('subarch')
    if release is None:
        release = factory.make_name('release')
    if label is None:
        label = factory.make_name('label')
    return ImageSpec(
        os,
        arch,
        subarch,
        release,
        label,
        )


def make_boot_image_mapping(image_specs=[]):
    mapping = BootImageMapping()
    for image_spec in image_specs:
        mapping.setdefault(image_spec, {})
    return mapping


class TestHelpers(MAASServerTestCase):

    def setUp(self):
        super(TestHelpers, self).setUp()
        self.useFixture(UpdateBootSourceCacheDisconnected())

    def test_ensure_boot_source_definition_creates_default_source(self):
        BootSource.objects.all().delete()
        ensure_boot_source_definition()
        sources = BootSource.objects.all()
        self.assertThat(sources, HasLength(1))
        [source] = sources
        self.assertAttributes(
            source,
            {
                'url': 'http://maas.ubuntu.com/images/ephemeral-v2/releases/',
                'keyring_filename': (
                    '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'),
            })
        selections = BootSourceSelection.objects.filter(boot_source=source)
        by_release = {
            selection.release: selection
            for selection in selections
            }
        self.assertItemsEqual(['trusty'], by_release.keys())
        self.assertAttributes(
            by_release['trusty'],
            {
                'release': 'trusty',
                'arches': ['amd64'],
                'subarches': ['*'],
                'labels': ['release'],
            })

    def test_ensure_boot_source_definition_skips_if_already_present(self):
        sources = [
            factory.make_BootSource()
            for _ in range(3)
            ]
        ensure_boot_source_definition()
        self.assertItemsEqual(sources, BootSource.objects.all())

    def test_get_boot_sources(self):
        sources = [
            factory.make_BootSource(
                keyring_data="data").to_dict()
            for _ in range(3)
            ]
        self.assertItemsEqual(sources, get_boot_sources())


class TestGetOSInfoFromBootSources(MAASServerTestCase):

    def setUp(self):
        super(TestGetOSInfoFromBootSources, self).setUp()
        self.useFixture(UpdateBootSourceCacheDisconnected())

    def test__returns_empty_sources_and_sets_when_cache_empty(self):
        self.assertEqual(
            ([], set(), set()),
            get_os_info_from_boot_sources(factory.make_name('os')))

    def test__returns_empty_sources_and_sets_when_no_os(self):
        factory.make_BootSourceCache()
        self.assertEqual(
            ([], set(), set()),
            get_os_info_from_boot_sources(factory.make_name('os')))

    def test__returns_sources_and_sets_of_releases_and_architectures(self):
        os = factory.make_name('os')
        sources = [
            factory.make_BootSource(keyring_data='1234') for _ in range(2)]
        releases = set()
        arches = set()
        for source in sources:
            for _ in range(3):
                release = factory.make_name('release')
                arch = factory.make_name('arch')
                factory.make_BootSourceCache(
                    source, os=os, release=release, arch=arch)
                releases.add(release)
                arches.add(arch)
        self.assertEqual(
            (sources, releases, arches),
            get_os_info_from_boot_sources(os))


class TestPrivateCacheBootSources(MAASTransactionServerTestCase):

    def setUp(self):
        super(TestPrivateCacheBootSources, self).setUp()
        self.useFixture(SimplestreamsEnvFixture())
        self.useFixture(UpdateBootSourceCacheDisconnected())

    def test__has_env_GNUPGHOME_set(self):
        capture = (
            patch_and_capture_env_for_download_all_image_descriptions(self))
        factory.make_BootSource(keyring_data=b'1234')
        cache_boot_sources()
        self.assertEqual(
            bootsources.get_maas_user_gpghome(),
            capture.env['GNUPGHOME'])

    def test__has_env_http_and_https_proxy_set(self):
        proxy_address = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy_address)
        capture = (
            patch_and_capture_env_for_download_all_image_descriptions(self))
        factory.make_BootSource(keyring_data=b'1234')
        cache_boot_sources()
        self.assertEqual(
            (proxy_address, proxy_address),
            (capture.env['http_proxy'], capture.env['https_proxy']))

    def test__doesnt_have_env_http_and_https_proxy_set_if_disabled(self):
        proxy_address = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy_address)
        Config.objects.set_config('enable_http_proxy', False)
        capture = (
            patch_and_capture_env_for_download_all_image_descriptions(self))
        factory.make_BootSource(keyring_data=b'1234')
        cache_boot_sources()
        self.assertEqual(
            ("", ""),
            (capture.env['http_proxy'], capture.env['https_proxy']))

    def test__returns_clears_entire_cache(self):
        source = factory.make_BootSource(keyring_data=b'1234')
        factory.make_BootSourceCache(source)
        mock_download = self.patch(
            bootsources, 'download_all_image_descriptions')
        mock_download.return_value = make_boot_image_mapping()
        cache_boot_sources()
        self.assertEqual(0, BootSourceCache.objects.all().count())

    def test__returns_adds_entries_to_cache_for_source(self):
        source = factory.make_BootSource(keyring_data=b'1234')
        os = factory.make_name('os')
        releases = [factory.make_name('release') for _ in range(3)]
        image_specs = [
            make_image_spec(os=os, release=release) for release in releases]
        mock_download = self.patch(
            bootsources, 'download_all_image_descriptions')
        mock_download.return_value = make_boot_image_mapping(image_specs)

        cache_boot_sources()
        cached_releases = [
            cache.release
            for cache in BootSourceCache.objects.filter(boot_source=source)
            if cache.os == os
            ]
        self.assertItemsEqual(releases, cached_releases)


class TestBadConnectionHandling(MAASTransactionServerTestCase):

    def setUp(self):
        super(TestBadConnectionHandling, self).setUp()
        self.useFixture(SimplestreamsEnvFixture())
        self.useFixture(UpdateBootSourceCacheDisconnected())

    def test__catches_connection_errors_and_sets_component_error(self):
        sources = [
            factory.make_BootSource(keyring_data=b'1234') for _ in range(3)]
        download_image_descriptions = self.patch(
            download_descriptions_module, 'download_image_descriptions')
        error_text = factory.make_name("error_text")
        # Make two of the downloads fail.
        download_image_descriptions.side_effect = [
            ConnectionError(error_text),
            BootImageMapping(),
            IOError(error_text),
            ]
        cache_boot_sources()
        base_error = "Failed to import images from boot source {url}: {err}"
        error_part_one = base_error.format(url=sources[0].url, err=error_text)
        error_part_two = base_error.format(url=sources[2].url, err=error_text)
        expected_error = error_part_one + '\n' + error_part_two
        actual_error = get_persistent_error(COMPONENT.REGION_IMAGE_IMPORT)
        self.assertEqual(expected_error, actual_error)

    def test__clears_component_error_when_successful(self):
        register_persistent_error(
            COMPONENT.REGION_IMAGE_IMPORT, factory.make_string())
        [factory.make_BootSource(keyring_data=b'1234') for _ in range(3)]
        download_image_descriptions = self.patch(
            download_descriptions_module, 'download_image_descriptions')
        # Make all of the downloads successful.
        download_image_descriptions.return_value = BootImageMapping()
        cache_boot_sources()
        self.assertIsNone(get_persistent_error(COMPONENT.REGION_IMAGE_IMPORT))
