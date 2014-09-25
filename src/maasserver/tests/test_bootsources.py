# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.bootsources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from os import environ

from maasserver import bootsources
from maasserver.bootsources import (
    ensure_boot_source_definition,
    get_boot_sources,
    get_os_info_from_boot_sources,
    )
from maasserver.models import (
    BootSource,
    BootSourceSelection,
    Config,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from mock import MagicMock
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
    )
from provisioningserver.import_images.helpers import ImageSpec
from testtools.matchers import HasLength


class TestHelpers(MAASServerTestCase):

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

    def patch_and_capture_env_for_download_all_image_descriptions(self):
        class CaptureEnv:
            """Fake function; records a copy of the environment."""

            def __call__(self, *args, **kwargs):
                self.args = args
                self.env = environ.copy()
                return MagicMock()

        capture = self.patch(
            bootsources, 'download_all_image_descriptions', CaptureEnv())
        return capture

    def make_os_image_spec(self, os=None):
        if os is None:
            os = factory.make_name('os')
        return ImageSpec(
            os,
            factory.make_name('arch'),
            factory.make_name('subarch'),
            factory.make_name('release'),
            factory.make_name('label'),
            )

    def make_boot_image_mapping(self, image_specs=[]):
        mapping = BootImageMapping()
        for image_spec in image_specs:
            mapping.setdefault(image_spec, {})
        return mapping

    def test__has_env_GNUPGHOME_set(self):
        capture = (
            self.patch_and_capture_env_for_download_all_image_descriptions())
        factory.make_BootSource(keyring_data='1234')
        get_os_info_from_boot_sources(factory.make_name('os'))
        self.assertEqual(
            bootsources.get_maas_user_gpghome(),
            capture.env['GNUPGHOME'])

    def test__has_env_http_and_https_proxy_set(self):
        proxy_address = factory.make_name('proxy')
        Config.objects.set_config('http_proxy', proxy_address)
        capture = (
            self.patch_and_capture_env_for_download_all_image_descriptions())
        factory.make_BootSource(keyring_data='1234')
        get_os_info_from_boot_sources(factory.make_name('os'))
        self.assertEqual(
            (proxy_address, proxy_address),
            (capture.env['http_proxy'], capture.env['http_proxy']))

    def test__returns_empty_sources_and_sets_when_descriptions_empty(self):
        factory.make_BootSource(keyring_data='1234')
        mock_download = self.patch(
            bootsources, 'download_all_image_descriptions')
        mock_download.return_value = self.make_boot_image_mapping()
        self.assertEqual(
            ([], set(), set()),
            get_os_info_from_boot_sources(factory.make_name('os')))

    def test__returns_empty_sources_and_sets_when_no_os(self):
        factory.make_BootSource(keyring_data='1234')
        image_specs = [
            self.make_os_image_spec()
            for _ in range(3)
            ]
        mock_download = self.patch(
            bootsources, 'download_all_image_descriptions')
        mock_download.return_value = self.make_boot_image_mapping(image_specs)
        self.assertEqual(
            ([], set(), set()),
            get_os_info_from_boot_sources(factory.make_name('os')))

    def test__returns_sources_and_sets_of_releases_and_architectures(self):
        os = factory.make_name('os')
        sources = [
            factory.make_BootSource(keyring_data='1234') for _ in range(2)]
        mappings = []
        releases = set()
        arches = set()
        for _ in sources:
            image_specs = [self.make_os_image_spec(os) for _ in range(3)]
            releases = releases.union(
                {image_spec.release for image_spec in image_specs})
            arches = arches.union(
                {image_spec.arch for image_spec in image_specs})
            mappings.append(self.make_boot_image_mapping(image_specs))
        mock_download = self.patch(
            bootsources, 'download_all_image_descriptions')
        mock_download.side_effect = mappings
        self.assertEqual(
            (sources, releases, arches),
            get_os_info_from_boot_sources(os))
