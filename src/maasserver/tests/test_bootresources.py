# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Test maasserver.bootresources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import httplib
import json
from random import randint
from StringIO import StringIO

from django.core.urlresolvers import reverse
from django.db import transaction
from django.http import StreamingHttpResponse
from django.test.client import Client
from maasserver.bootresources import (
    ensure_boot_source_definition,
    get_simplestream_endpoint,
    )
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    )
from maasserver.models import (
    BootSource,
    BootSourceSelection,
    )
from maasserver.testing.factory import factory
from maasserver.testing.testcase import MAASServerTestCase
from maasserver.utils import absolute_reverse
from maastesting.testcase import MAASTestCase
from testtools.matchers import (
    ContainsAll,
    HasLength,
    )


def make_boot_resource_file_with_stream():
    resource = factory.make_usable_boot_resource(
        rtype=BOOT_RESOURCE_TYPE.SYNCED)
    rfile = resource.sets.first().files.first()
    with rfile.largefile.content.open('rb') as stream:
        content = stream.read()
    with rfile.largefile.content.open('wb') as stream:
        stream.truncate()
    return rfile, StringIO(content), content


class TestHelpers(MAASServerTestCase):
    """Tests for `maasserver.bootresources` helpers."""

    def test_get_simplestreams_endpoint(self):
        endpoint = get_simplestream_endpoint()
        self.assertEqual(
            absolute_reverse(
                'simplestreams_stream_handler',
                kwargs={'filename': 'index.json'}),
            endpoint['url'])
        self.assertEqual([], endpoint['selections'])

    def test_ensure_boot_source_definition_creates_default_source(self):
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
            factory.make_boot_source()
            for _ in range(3)
            ]
        ensure_boot_source_definition()
        self.assertItemsEqual(sources, BootSource.objects.all())


class TestSimpleStreamsHandler(MAASServerTestCase):
    """Tests for `maasserver.bootresources.SimpleStreamsHandler`."""

    def reverse_stream_handler(self, filename):
        return reverse(
            'simplestreams_stream_handler', kwargs={'filename': filename})

    def reverse_file_handler(
            self, os, arch, subarch, series, version, filename):
        return reverse(
            'simplestreams_file_handler', kwargs={
                'os': os,
                'arch': arch,
                'subarch': subarch,
                'series': series,
                'version': version,
                'filename': filename,
                })

    def get_stream_client(self, filename):
        return self.client.get(self.reverse_stream_handler(filename))

    def get_file_client(self, os, arch, subarch, series, version, filename):
        return self.client.get(
            self.reverse_file_handler(
                os, arch, subarch, series, version, filename))

    def get_product_name_for_resource(self, resource):
        arch, subarch = resource.architecture.split('/')
        if resource.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            os = 'custom'
            series = resource.name
        else:
            os, series = resource.name.split('/')
        return 'maas:boot:%s:%s:%s:%s' % (os, arch, subarch, series)

    def make_usable_product_boot_resource(self):
        resource = factory.make_usable_boot_resource()
        return self.get_product_name_for_resource(resource), resource

    def test_streams_other_than_allowed_returns_404(self):
        allowed_paths = [
            'index.json',
            'maas:v2:download.json',
            ]
        invalid_paths = [
            '%s.json' % factory.make_name('path')
            for _ in range(3)
            ]
        for path in allowed_paths:
            response = self.get_stream_client(path)
            self.assertEqual(httplib.OK, response.status_code)
        for path in invalid_paths:
            response = self.get_stream_client(path)
            self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_streams_product_index_contains_keys(self):
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertThat(output, ContainsAll(['index', 'updated', 'format']))

    def test_streams_product_index_format_is_index_1(self):
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertEqual('index:1.0', output['format'])

    def test_streams_product_index_index_has_maas_v2_download(self):
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertThat(output['index'], ContainsAll(['maas:v2:download']))

    def test_streams_product_index_maas_v2_download_contains_keys(self):
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertThat(
            output['index']['maas:v2:download'],
            ContainsAll([
                'datatype', 'path', 'updated', 'products', 'format']))

    def test_streams_product_index_maas_v2_download_has_valid_values(self):
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertEqual(
            'image-downloads',
            output['index']['maas:v2:download']['datatype'])
        self.assertEqual(
            'streams/v1/maas:v2:download.json',
            output['index']['maas:v2:download']['path'])
        self.assertEqual(
            'products:1.0',
            output['index']['maas:v2:download']['format'])

    def test_streams_product_index_empty_products(self):
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertEqual(
            [],
            output['index']['maas:v2:download']['products'])

    def test_streams_product_index_empty_with_incomplete_resource(self):
        resource = factory.make_boot_resource()
        factory.make_boot_resource_set(resource)
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        self.assertEqual(
            [],
            output['index']['maas:v2:download']['products'])

    def test_streams_product_index_with_resources(self):
        products = []
        for _ in range(3):
            product, _ = self.make_usable_product_boot_resource()
            products.append(product)
        response = self.get_stream_client('index.json')
        output = json.loads(response.content)
        # Product listing should be the same as all of the completed
        # boot resources in the database.
        self.assertItemsEqual(
            products,
            output['index']['maas:v2:download']['products'])

    def test_streams_product_download_contains_keys(self):
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        self.assertThat(output, ContainsAll([
            'datatype', 'updated', 'content_id', 'products', 'format']))

    def test_streams_product_download_has_valid_values(self):
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        self.assertEqual('image-downloads', output['datatype'])
        self.assertEqual('maas:v2:download', output['content_id'])
        self.assertEqual('products:1.0', output['format'])

    def test_streams_product_download_empty_products(self):
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        self.assertEqual(
            {},
            output['products'])

    def test_streams_product_download_empty_with_incomplete_resource(self):
        resource = factory.make_boot_resource()
        factory.make_boot_resource_set(resource)
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        self.assertEqual(
            {},
            output['products'])

    def test_streams_product_download_has_valid_product_keys(self):
        products = []
        for _ in range(3):
            product, _ = self.make_usable_product_boot_resource()
            products.append(product)
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        # Product listing should be the same as all of the completed
        # boot resources in the database.
        self.assertThat(
            output['products'],
            ContainsAll(products))

    def test_streams_product_download_product_contains_keys(self):
        product, _ = self.make_usable_product_boot_resource()
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        self.assertThat(
            output['products'][product],
            ContainsAll([
                'versions', 'subarch', 'label', 'version',
                'arch', 'release', 'krel', 'os']))

    def test_streams_product_download_product_has_valid_values(self):
        product, resource = self.make_usable_product_boot_resource()
        _, _, os, arch, subarch, series = product.split(':')
        label = resource.get_latest_complete_set().label
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        output_product = output['products'][product]
        self.assertEqual(subarch, output_product['subarch'])
        self.assertEqual(label, output_product['label'])
        self.assertEqual(series, output_product['version'])
        self.assertEqual(arch, output_product['arch'])
        self.assertEqual(series, output_product['release'])
        self.assertEqual(series, output_product['krel'])
        self.assertEqual(os, output_product['os'])
        for key, value in resource.extra.items():
            self.assertEqual(value, output_product[key])

    def test_streams_product_download_product_uses_latest_complete_label(self):
        product, resource = self.make_usable_product_boot_resource()
        # Incomplete resource_set
        factory.make_boot_resource_set(resource)
        newest_set = factory.make_boot_resource_set(resource)
        factory.make_boot_resource_file_with_content(newest_set)
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        output_product = output['products'][product]
        self.assertEqual(newest_set.label, output_product['label'])

    def test_streams_product_download_product_contains_multiple_versions(self):
        resource = factory.make_boot_resource()
        resource_sets = [
            factory.make_boot_resource_set(resource)
            for _ in range(3)
            ]
        versions = []
        for resource_set in resource_sets:
            factory.make_boot_resource_file_with_content(resource_set)
            versions.append(resource_set.version)
        product = self.get_product_name_for_resource(resource)
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        self.assertThat(
            output['products'][product]['versions'],
            ContainsAll(versions))

    def test_streams_product_download_product_version_contains_items(self):
        product, resource = self.make_usable_product_boot_resource()
        resource_set = resource.get_latest_complete_set()
        items = [
            rfile.filename
            for rfile in resource_set.files.all()
            ]
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        version = output['products'][product]['versions'][resource_set.version]
        self.assertThat(
            version['items'],
            ContainsAll(items))

    def test_streams_product_download_product_item_contains_keys(self):
        product, resource = self.make_usable_product_boot_resource()
        resource_set = resource.get_latest_complete_set()
        resource_file = resource_set.files.order_by('?')[0]
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        version = output['products'][product]['versions'][resource_set.version]
        self.assertThat(
            version['items'][resource_file.filename],
            ContainsAll(['path', 'ftype', 'sha256', 'size']))

    def test_streams_product_download_product_item_has_valid_values(self):
        product, resource = self.make_usable_product_boot_resource()
        _, _, os, arch, subarch, series = product.split(':')
        resource_set = resource.get_latest_complete_set()
        resource_file = resource_set.files.order_by('?')[0]
        path = '%s/%s/%s/%s/%s/%s' % (
            os, arch, subarch, series, resource_set.version,
            resource_file.filename)
        response = self.get_stream_client('maas:v2:download.json')
        output = json.loads(response.content)
        version = output['products'][product]['versions'][resource_set.version]
        item = version['items'][resource_file.filename]
        self.assertEqual(path, item['path'])
        self.assertEqual(resource_file.filetype, item['ftype'])
        self.assertEqual(resource_file.largefile.sha256, item['sha256'])
        self.assertEqual(resource_file.largefile.total_size, item['size'])
        for key, value in resource_file.extra.items():
            self.assertEqual(value, item[key])

    def test_download_invalid_boot_resource_returns_404(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        arch = factory.make_name('arch')
        subarch = factory.make_name('subarch')
        version = factory.make_name('version')
        filename = factory.make_name('filename')
        response = self.get_file_client(
            os, arch, subarch, series, version, filename)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_download_invalid_version_returns_404(self):
        product, resource = self.make_usable_product_boot_resource()
        _, _, os, arch, subarch, series = product.split(':')
        version = factory.make_name('version')
        filename = factory.make_name('filename')
        response = self.get_file_client(
            os, arch, subarch, series, version, filename)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_download_invalid_filename_returns_404(self):
        product, resource = self.make_usable_product_boot_resource()
        _, _, os, arch, subarch, series = product.split(':')
        resource_set = resource.get_latest_complete_set()
        version = resource_set.version
        filename = factory.make_name('filename')
        response = self.get_file_client(
            os, arch, subarch, series, version, filename)
        self.assertEqual(httplib.NOT_FOUND, response.status_code)

    def test_download_valid_path_returns_200(self):
        product, resource = self.make_usable_product_boot_resource()
        _, _, os, arch, subarch, series = product.split(':')
        resource_set = resource.get_latest_complete_set()
        version = resource_set.version
        resource_file = resource_set.files.order_by('?')[0]
        filename = resource_file.filename
        response = self.get_file_client(
            os, arch, subarch, series, version, filename)
        self.assertEqual(httplib.OK, response.status_code)

    def test_download_returns_streaming_response(self):
        product, resource = self.make_usable_product_boot_resource()
        _, _, os, arch, subarch, series = product.split(':')
        resource_set = resource.get_latest_complete_set()
        version = resource_set.version
        resource_file = resource_set.files.order_by('?')[0]
        filename = resource_file.filename
        with resource_file.largefile.content.open('rb') as stream:
            content = stream.read()
        response = self.get_file_client(
            os, arch, subarch, series, version, filename)
        self.assertIsInstance(response, StreamingHttpResponse)
        self.assertEqual(content, b''.join(response.streaming_content))


class TestTransactionWrapper(MAASTestCase):
    """Tests the use of StreamingHttpResponse(TransactionWrapper(stream)).

    We do not run this inside of `MAASServerTestCase` as that wraps a
    transaction around each test. This removes that behavior so we can
    test that the transaction is remaining open for all of the content.
    """

    def test_download(self):
        # Do the setup inside of a transaction, as we are running in a test
        # that doesn't enable transactions per test.
        with transaction.atomic():
            os = factory.make_name('os')
            series = factory.make_name('series')
            arch = factory.make_name('arch')
            subarch = factory.make_name('subarch')
            name = '%s/%s' % (os, series)
            architecture = '%s/%s' % (arch, subarch)
            version = factory.make_name('version')
            filetype = factory.pick_enum(BOOT_RESOURCE_FILE_TYPE)
            # We set the filename to the same value as filetype, as in most
            # cases this will always be true. The simplestreams content from
            # maas.ubuntu.com, is formatted this way.
            filename = filetype
            size = randint(1024, 2048)
            content = factory.make_string(size=size)
            resource = factory.make_boot_resource(
                rtype=BOOT_RESOURCE_TYPE.SYNCED, name=name,
                architecture=architecture)
            resource_set = factory.make_boot_resource_set(
                resource, version=version)
            largefile = factory.make_large_file(content=content, size=size)
            factory.make_boot_resource_file(
                resource_set, largefile, filename=filename, filetype=filetype)

        # Outside of the transaction, we run the actual test. The client will
        # run inside of its own transaction, but once the streaming response
        # is returned that transaction will be closed.
        client = Client()
        response = client.get(
            reverse(
                'simplestreams_file_handler', kwargs={
                    'os': os,
                    'arch': arch,
                    'subarch': subarch,
                    'series': series,
                    'version': version,
                    'filename': filename,
                    }))

        # If TransactionWrapper does not work, then a ProgramError will be
        # thrown. If it works then content will match.
        self.assertEqual(content, b''.join(response.streaming_content))
        self.assertTrue(largefile.content.closed)
