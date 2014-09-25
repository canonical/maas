# Copyright 2012-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver images views."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import random

from django.core.urlresolvers import reverse
from lxml.html import fromstring
from maasserver.enum import (
    BOOT_RESOURCE_TYPE,
    NODE_STATUS,
    )
from maasserver.models import (
    BootSourceSelection,
    Config,
    )
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.views import images as images_view
from maastesting.matchers import MockCalledOnceWith
from requests import ConnectionError
from testtools.matchers import (
    Contains,
    ContainsAll,
    HasLength,
    )


class UbuntuImagesTest(MAASServerTestCase):

    def patch_get_os_info_from_boot_sources(
            self, sources, releases=None, arches=None):
        if releases is None:
            releases = [factory.make_name('release') for _ in range(3)]
        if arches is None:
            arches = [factory.make_name('arch') for _ in range(3)]
        mock_get_os_info = self.patch(
            images_view, 'get_os_info_from_boot_sources')
        mock_get_os_info.return_value = (sources, releases, arches)
        return mock_get_os_info

    def make_ubuntu_resource(self, release=None):
        if release is None:
            release = factory.make_name('release')
        name = 'ubuntu/%s' % release
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        architecture = '%s/%s' % (arch, subarch)
        return factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.SYNCED,
            name=name, architecture=architecture)

    def test_shows_connection_error(self):
        self.client_log_in(as_admin=True)
        mock_get_os_info = self.patch(
            images_view, 'get_os_info_from_boot_sources')
        mock_get_os_info.side_effect = ConnectionError()
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        warnings = doc.cssselect('div#connection-error')
        self.assertEqual(1, len(warnings))

    def test_shows_no_ubuntu_sources(self):
        self.client_log_in(as_admin=True)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        warnings = doc.cssselect('div#no-ubuntu-sources')
        self.assertEqual(1, len(warnings))

    def test_shows_too_many_ubuntu_sources(self):
        self.client_log_in(as_admin=True)
        sources = [factory.make_BootSource() for _ in range(2)]
        self.patch_get_os_info_from_boot_sources(sources)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        warnings = doc.cssselect('div#too-many-ubuntu-sources')
        self.assertEqual(1, len(warnings))

    def test_shows_release_options(self):
        self.client_log_in(as_admin=True)
        sources = [factory.make_BootSource()]
        releases = [factory.make_name('release') for _ in range(3)]
        self.patch_get_os_info_from_boot_sources(sources, releases=releases)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        releases_content = doc.cssselect(
            'ul#ubuntu-releases')[0].text_content()
        self.assertThat(releases_content, ContainsAll(releases))

    def test_shows_architecture_options(self):
        self.client_log_in(as_admin=True)
        sources = [factory.make_BootSource()]
        arches = [factory.make_name('arch') for _ in range(3)]
        self.patch_get_os_info_from_boot_sources(sources, arches=arches)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        arches_content = doc.cssselect(
            'ul#ubuntu-arches')[0].text_content()
        self.assertThat(arches_content, ContainsAll(arches))

    def test_shows_missing_images_warning_if_not_ubuntu_boot_resources(self):
        self.client_log_in()
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        warnings = doc.cssselect('div#missing-ubuntu-images')
        self.assertEqual(1, len(warnings))

    def test_shows_ubuntu_resources(self):
        self.client_log_in()
        releases = [factory.make_name('release') for _ in range(3)]
        [self.make_ubuntu_resource(release) for release in releases]
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        table_content = doc.cssselect(
            'table#ubuntu-resources')[0].text_content()
        self.assertThat(table_content, ContainsAll(releases))

    def test_shows_ubuntu_release_version_name(self):
        self.client_log_in()
        # Use trusty as known to map to "14.04 LTS"
        release = 'trusty'
        version = '14.04 LTS'
        self.make_ubuntu_resource(release)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        table_content = doc.cssselect(
            'table#ubuntu-resources')[0].text_content()
        self.assertThat(table_content, Contains(version))

    def test_shows_number_of_nodes_deployed_for_ubuntu_resource(self):
        self.client_log_in()
        resource = self.make_ubuntu_resource()
        os_name, series = resource.name.split('/')
        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED,
                osystem=os_name, distro_series=series,
                architecture=resource.architecture)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        count = int(doc.cssselect(
            'table#ubuntu-resources > tbody > tr > td')[4].text_content())
        self.assertEqual(number_of_nodes, count)

    def test_shows_number_of_default_nodes_deployed_for_ubuntu_resource(self):
        self.client_log_in()
        resource = self.make_ubuntu_resource()
        os_name, series = resource.name.split('/')
        Config.objects.set_config('default_osystem', os_name)
        Config.objects.set_config('default_distro_series', series)
        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED,
                architecture=resource.architecture)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        count = int(doc.cssselect(
            'table#ubuntu-resources > tbody > tr > td')[4].text_content())
        self.assertEqual(number_of_nodes, count)

    def test_shows_number_of_nodes_deployed_for_ubuntu_subarch_resource(self):
        self.client_log_in()
        resource = self.make_ubuntu_resource()
        arch, subarch = resource.split_arch()
        extra_subarch = factory.make_name('subarch')
        resource.extra['subarches'] = ','.join([subarch, extra_subarch])
        resource.save()

        os_name, series = resource.name.split('/')
        node_architecture = '%s/%s' % (arch, extra_subarch)
        number_of_nodes = random.randint(1, 4)
        for _ in range(number_of_nodes):
            factory.make_Node(
                status=NODE_STATUS.DEPLOYED,
                osystem=os_name, distro_series=series,
                architecture=node_architecture)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        count = int(doc.cssselect(
            'table#ubuntu-resources > tbody > tr > td')[4].text_content())
        self.assertEqual(number_of_nodes, count)

    def test_hides_import_button_if_not_admin(self):
        self.client_log_in()
        sources = [factory.make_BootSource()]
        self.patch_get_os_info_from_boot_sources(sources)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        import_button = doc.cssselect(
            '#ubuntu-images')[0].cssselect('input[type="submit"]')
        self.assertEqual(0, len(import_button))

    def test_shows_import_button_if_admin(self):
        self.client_log_in(as_admin=True)
        sources = [factory.make_BootSource()]
        self.patch_get_os_info_from_boot_sources(sources)
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        import_button = doc.cssselect(
            '#ubuntu-images')[0].cssselect('input[type="submit"]')
        self.assertEqual(1, len(import_button))

    def test_hides_import_button_if_import_running(self):
        self.client_log_in()
        sources = [factory.make_BootSource()]
        self.patch_get_os_info_from_boot_sources(sources)
        self.patch(
            images_view, 'is_import_resources_running').return_value = True
        response = self.client.get(reverse('images'))
        doc = fromstring(response.content)
        import_button = doc.cssselect(
            '#ubuntu-images')[0].cssselect('input[type="submit"]')
        self.assertEqual(0, len(import_button))

    def test_post_returns_forbidden_if_not_admin(self):
        self.client_log_in()
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1})
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_import_calls_import_resources(self):
        self.client_log_in(as_admin=True)
        sources = [factory.make_BootSource()]
        self.patch_get_os_info_from_boot_sources(sources)
        mock_import = self.patch(images_view, 'import_resources')
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertThat(mock_import, MockCalledOnceWith())

    def test_import_sets_empty_selections(self):
        self.client_log_in(as_admin=True)
        source = factory.make_BootSource()
        self.patch_get_os_info_from_boot_sources([source])
        self.patch(images_view, 'import_resources')
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1})
        self.assertEqual(httplib.FOUND, response.status_code)

        selections = BootSourceSelection.objects.filter(boot_source=source)
        self.assertThat(selections, HasLength(1))
        self.assertEqual(
            (selections[0].os, selections[0].release,
                selections[0].arches, selections[0].subarches,
                selections[0].labels),
            ("ubuntu", "", [], ["*"], ["*"]))

    def test_import_sets_release_selections(self):
        self.client_log_in(as_admin=True)
        source = factory.make_BootSource()
        releases = [factory.make_name('release') for _ in range(3)]
        self.patch_get_os_info_from_boot_sources([source])
        self.patch(images_view, 'import_resources')
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1, 'release': releases})
        self.assertEqual(httplib.FOUND, response.status_code)

        selections = BootSourceSelection.objects.filter(boot_source=source)
        self.assertThat(selections, HasLength(len(releases)))
        self.assertItemsEqual(
            releases,
            [selection.release for selection in selections])

    def test_import_sets_arches_on_selections(self):
        self.client_log_in(as_admin=True)
        source = factory.make_BootSource()
        releases = [factory.make_name('release') for _ in range(3)]
        arches = [factory.make_name('arches') for _ in range(3)]
        self.patch_get_os_info_from_boot_sources([source])
        self.patch(images_view, 'import_resources')
        response = self.client.post(
            reverse('images'),
            {'ubuntu_images': 1, 'release': releases, 'arch': arches})
        self.assertEqual(httplib.FOUND, response.status_code)

        selections = BootSourceSelection.objects.filter(boot_source=source)
        self.assertThat(selections, HasLength(len(releases)))
        self.assertItemsEqual(
            [arches, arches, arches],
            [selection.arches for selection in selections])

    def test_import_removes_old_selections(self):
        self.client_log_in(as_admin=True)
        source = factory.make_BootSource()
        release = factory.make_name('release')
        delete_selection = BootSourceSelection.objects.create(
            boot_source=source, os='ubuntu',
            release=factory.make_name('release'))
        keep_selection = BootSourceSelection.objects.create(
            boot_source=source, os='ubuntu', release=release)
        self.patch_get_os_info_from_boot_sources([source])
        self.patch(images_view, 'import_resources')
        response = self.client.post(
            reverse('images'), {'ubuntu_images': 1, 'release': [release]})
        self.assertEqual(httplib.FOUND, response.status_code)
        self.assertIsNone(reload_object(delete_selection))
        self.assertIsNotNone(reload_object(keep_selection))
