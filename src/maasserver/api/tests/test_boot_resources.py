# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `Boot Resources` API."""

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
import random

from django.core.urlresolvers import reverse
from maasserver.api.boot_resources import (
    boot_resource_file_to_dict,
    boot_resource_set_to_dict,
    boot_resource_to_dict,
    )
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
    BOOT_RESOURCE_TYPE_CHOICES_DICT,
    )
from maasserver.models import BootResource
from maasserver.testing.api import APITestCase
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase
from maastesting.utils import sample_binary_data
from testtools.matchers import ContainsAll


def get_boot_resource_uri(resource):
    """Return a boot resource's URI on the API."""
    return reverse(
        'boot_resource_handler',
        args=[resource.id])


class TestHelpers(MAASServerTestCase):

    def test_boot_resource_file_to_dict(self):
        size = random.randint(512, 1023)
        total_size = random.randint(1024, 2048)
        content = factory.make_string(size)
        largefile = factory.make_large_file(content=content, size=total_size)
        resource = factory.make_boot_resource()
        resource_set = factory.make_boot_resource_set(resource)
        rfile = factory.make_boot_resource_file(resource_set, largefile)
        dict_representation = boot_resource_file_to_dict(rfile)
        self.assertEqual(rfile.filename, dict_representation['filename'])
        self.assertEqual(rfile.filetype, dict_representation['filetype'])
        self.assertEqual(rfile.largefile.sha256, dict_representation['sha256'])
        self.assertEqual(total_size, dict_representation['size'])
        self.assertEqual(False, dict_representation['complete'])
        self.assertEqual(
            rfile.largefile.progress, dict_representation['progress'])

    def test_boot_resource_set_to_dict(self):
        resource = factory.make_boot_resource()
        resource_set = factory.make_boot_resource_set(resource)
        total_size = random.randint(1024, 2048)
        content = factory.make_string(random.randint(512, 1023))
        largefile = factory.make_large_file(content=content, size=total_size)
        rfile = factory.make_boot_resource_file(resource_set, largefile)
        dict_representation = boot_resource_set_to_dict(resource_set)
        self.assertEqual(resource_set.version, dict_representation['version'])
        self.assertEqual(resource_set.label, dict_representation['label'])
        self.assertEqual(resource_set.total_size, dict_representation['size'])
        self.assertEqual(False, dict_representation['complete'])
        self.assertEqual(
            resource_set.progress, dict_representation['progress'])
        self.assertItemsEqual(
            boot_resource_file_to_dict(rfile),
            dict_representation['files'][rfile.filename])

    def test_boot_resource_to_dict_without_sets(self):
        resource = factory.make_boot_resource()
        factory.make_boot_resource_set(resource)
        dict_representation = boot_resource_to_dict(resource, with_sets=False)
        self.assertEqual(resource.id, dict_representation['id'])
        self.assertEqual(
            BOOT_RESOURCE_TYPE_CHOICES_DICT[resource.rtype],
            dict_representation['type'])
        self.assertEqual(resource.name, dict_representation['name'])
        self.assertEqual(
            resource.architecture, dict_representation['architecture'])
        self.assertEqual(
            get_boot_resource_uri(resource),
            dict_representation['resource_uri'])
        self.assertFalse('sets' in dict_representation)

    def test_boot_resource_to_dict_with_sets(self):
        resource = factory.make_boot_resource()
        resource_set = factory.make_boot_resource_set(resource)
        dict_representation = boot_resource_to_dict(resource, with_sets=True)
        self.assertItemsEqual(
            boot_resource_set_to_dict(resource_set),
            dict_representation['sets'][resource_set.version])


class TestBootSourcesAPI(APITestCase):
    """Test the the boot resource API."""

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/boot-resources/',
            reverse('boot_resources_handler'))

    def test_GET_returns_boot_resources_list(self):
        resources = [
            factory.make_boot_resource() for _ in range(3)]
        response = self.client.get(
            reverse('boot_resources_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [resource.id for resource in resources],
            [resource.get('id') for resource in parsed_result])

    def test_GET_synced_returns_synced_boot_resources(self):
        resources = [
            factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
            for _ in range(3)
            ]
        factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.GENERATED)
        factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        response = self.client.get(
            reverse('boot_resources_handler'), {'type': 'synced'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [resource.id for resource in resources],
            [resource.get('id') for resource in parsed_result])

    def test_GET_generated_returns_generated_boot_resources(self):
        resources = [
            factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.GENERATED)
            for _ in range(3)
            ]
        factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
        response = self.client.get(
            reverse('boot_resources_handler'), {'type': 'generated'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [resource.id for resource in resources],
            [resource.get('id') for resource in parsed_result])

    def test_GET_uploaded_returns_uploaded_boot_resources(self):
        resources = [
            factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.UPLOADED)
            for _ in range(3)
            ]
        factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.SYNCED)
        factory.make_boot_resource(rtype=BOOT_RESOURCE_TYPE.GENERATED)
        response = self.client.get(
            reverse('boot_resources_handler'), {'type': 'uploaded'})
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertItemsEqual(
            [resource.id for resource in resources],
            [resource.get('id') for resource in parsed_result])

    def test_GET_doesnt_include_full_definition_of_boot_resource(self):
        factory.make_boot_resource()
        response = self.client.get(
            reverse('boot_resources_handler'))
        self.assertEqual(httplib.OK, response.status_code, response.content)
        parsed_result = json.loads(response.content)
        self.assertFalse('sets' in parsed_result[0])

    def test_POST_requires_admin(self):
        params = {
            'name': factory.make_name('name'),
            'architecture': make_usable_architecture(self),
            'content': (
                factory.make_file_upload(content=sample_binary_data)),
        }
        response = self.client.post(
            reverse('boot_resources_handler'), params)
        self.assertEqual(httplib.FORBIDDEN, response.status_code)

    def test_POST_creates_boot_resource(self):
        self.become_admin()

        name = factory.make_name('name')
        architecture = make_usable_architecture(self)
        filetype = random.choice([
            BOOT_RESOURCE_FILE_TYPE.TGZ, BOOT_RESOURCE_FILE_TYPE.DDTGZ])
        params = {
            'name': name,
            'architecture': architecture,
            'filetype': filetype,
            'content': (
                factory.make_file_upload(content=sample_binary_data)),
        }
        response = self.client.post(
            reverse('boot_resources_handler'), params)
        self.assertEqual(httplib.CREATED, response.status_code)
        parsed_result = json.loads(response.content)

        resource = BootResource.objects.get(id=parsed_result['id'])
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertEqual(name, resource.name)
        self.assertEqual(architecture, resource.architecture)
        self.assertEqual('uploaded', resource_set.label)
        self.assertEqual(filetype, rfile.filename)
        self.assertEqual(filetype, rfile.filetype)
        with rfile.largefile.content.open('rb') as stream:
            written_data = stream.read()
        self.assertEqual(sample_binary_data, written_data)

    def test_POST_creates_boot_resource_with_default_filetype(self):
        self.become_admin()

        name = factory.make_name('name')
        architecture = make_usable_architecture(self)
        params = {
            'name': name,
            'architecture': architecture,
            'content': (
                factory.make_file_upload(content=sample_binary_data)),
        }
        response = self.client.post(
            reverse('boot_resources_handler'), params)
        self.assertEqual(httplib.CREATED, response.status_code)
        parsed_result = json.loads(response.content)

        resource = BootResource.objects.get(id=parsed_result['id'])
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertEqual(BOOT_RESOURCE_FILE_TYPE.TGZ, rfile.filetype)

    def test_POST_returns_full_definition_of_boot_resource(self):
        self.become_admin()

        name = factory.make_name('name')
        architecture = make_usable_architecture(self)
        params = {
            'name': name,
            'architecture': architecture,
            'content': (
                factory.make_file_upload(content=sample_binary_data)),
        }
        response = self.client.post(
            reverse('boot_resources_handler'), params)
        self.assertEqual(httplib.CREATED, response.status_code)
        parsed_result = json.loads(response.content)
        self.assertTrue('sets' in parsed_result)

    def test_POST_validates_boot_resource(self):
        self.become_admin()

        params = {
            'name': factory.make_name('name'),
        }
        response = self.client.post(
            reverse('boot_resources_handler'), params)
        self.assertEqual(httplib.BAD_REQUEST, response.status_code)


class TestBootResourceAPI(APITestCase):

    def test_handler_path(self):
        self.assertEqual(
            '/api/1.0/boot-resources/3/',
            reverse('boot_resource_handler', args=['3']))

    def test_GET_returns_boot_resource(self):
        resource = factory.make_usable_boot_resource()
        response = self.client.get(get_boot_resource_uri(resource))
        self.assertEqual(httplib.OK, response.status_code)
        returned_resource = json.loads(response.content)
        # The returned object contains a 'resource_uri' field.
        self.assertEqual(
            reverse(
                'boot_resource_handler',
                args=[resource.id]
            ),
            returned_resource['resource_uri'])
        self.assertThat(
            returned_resource,
            ContainsAll(['id', 'type', 'name', 'architecture']))

    def test_DELETE_deletes_boot_resource(self):
        self.become_admin()
        resource = factory.make_boot_resource()
        response = self.client.delete(get_boot_resource_uri(resource))
        self.assertEqual(httplib.NO_CONTENT, response.status_code)
        self.assertIsNone(reload_object(resource))

    def test_DELETE_requires_admin(self):
        resource = factory.make_boot_resource()
        response = self.client.delete(get_boot_resource_uri(resource))
        self.assertEqual(httplib.FORBIDDEN, response.status_code)
