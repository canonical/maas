# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `BootSourceForm`."""

__all__ = []

import random

from django.core.files.uploadedfile import SimpleUploadedFile
from maasserver.enum import (
    BOOT_RESOURCE_FILE_TYPE,
    BOOT_RESOURCE_TYPE,
)
from maasserver.forms import BootResourceForm
from maasserver.models import BootResource
from maasserver.testing.architecture import make_usable_architecture
from maasserver.testing.factory import factory
from maasserver.testing.orm import reload_object
from maasserver.testing.testcase import MAASServerTestCase


class TestBootResourceForm(MAASServerTestCase):

    def pick_filetype(self):
        upload_type = random.choice([
            'tgz', 'ddtgz'])
        if upload_type == 'tgz':
            filetype = BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ
        elif upload_type == 'ddtgz':
            filetype = BOOT_RESOURCE_FILE_TYPE.ROOT_DD
        return upload_type, filetype

    def test_creates_boot_resource(self):
        name = factory.make_name('name')
        title = factory.make_name('title')
        architecture = make_usable_architecture(self)
        subarch = architecture.split('/')[1]
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode('utf-8')
        upload_name = factory.make_name('filename')
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            'name': name,
            'title': title,
            'architecture': architecture,
            'filetype': upload_type,
            }
        form = BootResourceForm(data=data, files={'content': uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = BootResource.objects.get(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name, architecture=architecture)
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertEqual(title, resource.extra['title'])
        self.assertEqual(subarch, resource.extra['subarches'])
        self.assertTrue(filetype, rfile.filetype)
        self.assertTrue(filetype, rfile.filename)
        self.assertTrue(size, rfile.largefile.total_size)
        with rfile.largefile.content.open('rb') as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_adds_boot_resource_set_to_existing_boot_resource(self):
        name = factory.make_name('name')
        architecture = make_usable_architecture(self)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.UPLOADED,
            name=name, architecture=architecture)
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode('utf-8')
        upload_name = factory.make_name('filename')
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            'name': name,
            'architecture': architecture,
            'filetype': upload_type,
            }
        form = BootResourceForm(data=data, files={'content': uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = reload_object(resource)
        resource_set = resource.sets.order_by('id').last()
        rfile = resource_set.files.first()
        self.assertTrue(filetype, rfile.filetype)
        self.assertTrue(filetype, rfile.filename)
        self.assertTrue(size, rfile.largefile.total_size)
        with rfile.largefile.content.open('rb') as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_creates_boot_resoures_with_generated_rtype(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        architecture = make_usable_architecture(self)
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode('utf-8')
        upload_name = factory.make_name('filename')
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            'name': name,
            'architecture': architecture,
            'filetype': upload_type,
            }
        form = BootResourceForm(data=data, files={'content': uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = BootResource.objects.get(
            rtype=BOOT_RESOURCE_TYPE.GENERATED,
            name=name, architecture=architecture)
        resource_set = resource.sets.first()
        rfile = resource_set.files.first()
        self.assertTrue(filetype, rfile.filetype)
        self.assertTrue(filetype, rfile.filename)
        self.assertTrue(size, rfile.largefile.total_size)
        with rfile.largefile.content.open('rb') as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_adds_boot_resource_set_to_existing_generated_boot_resource(self):
        os = factory.make_name('os')
        series = factory.make_name('series')
        name = '%s/%s' % (os, series)
        architecture = make_usable_architecture(self)
        resource = factory.make_usable_boot_resource(
            rtype=BOOT_RESOURCE_TYPE.GENERATED,
            name=name, architecture=architecture)
        upload_type, filetype = self.pick_filetype()
        size = random.randint(1024, 2048)
        content = factory.make_string(size).encode('utf-8')
        upload_name = factory.make_name('filename')
        uploaded_file = SimpleUploadedFile(content=content, name=upload_name)
        data = {
            'name': name,
            'architecture': architecture,
            'filetype': upload_type,
            }
        form = BootResourceForm(data=data, files={'content': uploaded_file})
        self.assertTrue(form.is_valid(), form._errors)
        form.save()
        resource = reload_object(resource)
        resource_set = resource.sets.order_by('id').last()
        rfile = resource_set.files.first()
        self.assertTrue(filetype, rfile.filetype)
        self.assertTrue(filetype, rfile.filename)
        self.assertTrue(size, rfile.largefile.total_size)
        with rfile.largefile.content.open('rb') as stream:
            written_content = stream.read()
        self.assertEqual(content, written_content)

    def test_requires_fields(self):
        form = BootResourceForm(data={})
        self.assertFalse(form.is_valid(), form.errors)
        self.assertItemsEqual([
            'name', 'architecture', 'filetype', 'content',
            ],
            form.errors.keys())
