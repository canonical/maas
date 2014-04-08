# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the boot_resources module."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import errno
import hashlib
import json
import os
from random import randint
from subprocess import (
    PIPE,
    Popen,
    )

from maastesting.factory import factory
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver.boot.uefi import UEFIBootMethod
from provisioningserver.config import BootConfig
from provisioningserver.import_images import boot_resources
from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
    )
from provisioningserver.import_images.testing.factory import (
    make_boot_resource,
    make_image_spec,
    set_resource,
    )
from provisioningserver.utils import write_text_file
from testtools.content import Content
from testtools.content_type import UTF8_TEXT
from testtools.matchers import (
    DirExists,
    FileExists,
    )
import yaml


class TestBootReverse(MAASTestCase):
    """Tests for `boot_reverse`."""

    def test_maps_empty_dict_to_empty_dict(self):
        empty_boot_image_dict = BootImageMapping()
        self.assertEqual(
            {},
            boot_resources.boot_reverse(empty_boot_image_dict).mapping)

    def test_maps_boot_resource_by_content_id_product_name_and_version(self):
        image = make_image_spec()
        resource = make_boot_resource()
        boot_dict = set_resource(resource=resource.copy(), image_spec=image)
        self.assertEqual(
            {
                (
                    resource['content_id'],
                    resource['product_name'],
                    resource['version_name'],
                ): [image.subarch],
            },
            boot_resources.boot_reverse(boot_dict).mapping)

    def test_concatenates_similar_resources(self):
        image1 = make_image_spec()
        image2 = make_image_spec()
        resource = make_boot_resource()
        boot_dict = BootImageMapping()
        # Create two images in boot_dict, both containing the same resource.
        for image in [image1, image2]:
            set_resource(
                boot_dict=boot_dict, resource=resource.copy(),
                image_spec=image)

        reverse_dict = boot_resources.boot_reverse(boot_dict)
        key = (
            resource['content_id'],
            resource['product_name'],
            resource['version_name'],
            )
        self.assertEqual([key], reverse_dict.mapping.keys())
        self.assertItemsEqual(
            [image1.subarch, image2.subarch],
            reverse_dict.get(resource))


class TestTgtEntry(MAASTestCase):
    """Tests for `tgt_entry`."""

    def test_generates_one_target(self):
        spec = make_image_spec()
        image = self.make_file()
        entry = boot_resources.tgt_entry(
            spec.arch, spec.subarch, spec.release, spec.label, image)
        # The entry looks a bit like XML, but isn't well-formed.  So don't try
        # to parse it as such!
        self.assertIn('<target iqn.2004-05.com.ubuntu:maas:', entry)
        self.assertIn('backing-store "%s"' % image, entry)
        self.assertEqual(1, entry.count('</target>'))

    def test_produces_suitable_output_for_tgt_admin(self):
        spec = make_image_spec()
        image = self.make_file()
        entry = boot_resources.tgt_entry(
            spec.arch, spec.subarch, spec.release, spec.label, image)
        config = self.make_file(contents=entry)
        # Pretend to be root, but without requiring the actual privileges and
        # without prompting for a password.  In that state, run tgt-admin.
        # It has to think it's root, even for a "pretend" run.
        # Make it read the config we just produced, and pretend to update its
        # iSCSI targets based on what it finds in the config.
        #
        # The only real test is that this succeed.
        cmd = Popen(
            [
                'fakeroot', 'tgt-admin',
                '--conf', config,
                '--pretend',
                '--update', 'ALL',
            ],
            stdout=PIPE, stderr=PIPE)
        stdout, stderr = cmd.communicate()
        self.addDetail('tgt-stderr', Content(UTF8_TEXT, lambda: [stderr]))
        self.addDetail('tgt-stdout', Content(UTF8_TEXT, lambda: [stdout]))
        self.assertEqual(0, cmd.returncode)


def checksum_sha256(data):
    """Return the SHA256 checksum for `data`, as a hex string."""
    assert isinstance(data, bytes)
    summer = hashlib.sha256()
    summer.update(data)
    return summer.hexdigest()


class TestMain(MAASTestCase):

    def patch_logger(self):
        """Suppress log output from the import code."""
        self.patch(boot_resources, 'logger')

    def make_args(self, **kwargs):
        """Fake an `argumentparser` parse result."""
        args = mock.Mock()
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    def make_simplestreams_index(self, index_dir, stream, product):
        """Write a fake simplestreams index file.  Return its path."""
        index_file = os.path.join(index_dir, 'index.json')
        index = {
            'format': 'index:1.0',
            'updated': 'Tue, 25 Mar 2014 16:19:49 +0000',
            'index': {
                stream: {
                    'datatype': 'image-ids',
                    'path': 'streams/v1/%s.json' % stream,
                    'updated': 'Tue, 25 Mar 2014 16:19:49 +0000',
                    'format': 'products:1.0',
                    'products': [product],
                    },
                },
            }
        write_text_file(index_file, json.dumps(index))
        return index_file

    def make_download_file(self, repo, image_spec, version,
                           filename='boot-kernel'):
        """Fake a downloadable file in `repo`.

        Return the new file's POSIX path, and its contents.
        """
        path = [
            image_spec.release,
            image_spec.arch,
            version,
            image_spec.release,
            image_spec.subarch,
            filename,
            ]
        native_path = os.path.join(repo, *path)
        os.makedirs(os.path.dirname(native_path))
        contents = ("Contents: %s" % filename).encode('utf-8')
        write_text_file(native_path, contents)
        # Return POSIX path for inclusion in Simplestreams data, not
        # system-native path for filesystem access.
        return '/'.join(path), contents

    def make_simplestreams_product_index(self, index_dir, stream, product,
                                         image_spec, os_release,
                                         download_file, contents, version):
        """Write a fake Simplestreams product index file.

        The image is written into the directory that holds the indexes.  It
        contains one downloadable file, as specified by the arguments.
        """
        index = {
            'format': 'products:1.0',
            'data-type': 'image-ids',
            'updated': 'Tue, 25 Mar 2014 16:19:49 +0000',
            'content_id': stream,
            'products': {
                product: {
                    'versions': {
                        version: {
                            'items': {
                                'boot-kernel': {
                                    'ftype': 'boot-kernel',
                                    '_fake': 'fake-data: %s' % download_file,
                                    'version': os_release,
                                    'release': image_spec.release,
                                    'path': download_file,
                                    'sha256': checksum_sha256(contents),
                                    'arch': image_spec.arch,
                                    'subarches': image_spec.subarch,
                                    'size': len(contents),
                                },
                            },
                        },
                    },
                    'subarch': image_spec.subarch,
                    'krel': image_spec.release,
                    'label': image_spec.label,
                    'kflavor': image_spec.subarch,
                    'version': os_release,
                    'subarches': [image_spec.subarch],
                    'release': image_spec.release,
                    'arch': image_spec.arch,
                },
            },
        }
        write_text_file(
            os.path.join(index_dir, '%s.json' % stream),
            json.dumps(index))

    def make_simplestreams_repo(self, image_spec):
        """Fake a local simplestreams repository containing the given image.

        This creates a temporary directory that looks like a realistic
        Simplestreams repository, containing one downloadable file for the
        given `image_spec`.
        """
        os_release = '%d.%.2s' % (
            randint(1, 99),
            ('04' if randint(0, 1) == 0 else '10'),
            )
        repo = self.make_dir()
        index_dir = os.path.join(repo, 'streams', 'v1')
        os.makedirs(index_dir)
        stream = 'com.ubuntu.maas:daily:v2:download'
        product = 'com.ubuntu.maas:boot:%s:%s:%s' % (
            os_release,
            image_spec.arch,
            image_spec.subarch,
            )
        version = '20140317'
        download_file, sha = self.make_download_file(repo, image_spec, version)
        self.make_simplestreams_product_index(
            index_dir, stream, product, image_spec, os_release, download_file,
            sha, version)
        index = self.make_simplestreams_index(index_dir, stream, product)
        return index

    def test_successful_run(self):
        """Integration-test a successful run of the importer.

        This runs as much realistic code as it can, exercising most of the
        integration points for a real import.
        """
        # Patch out things that we don't want running during the test.  Patch
        # at a low level, so that we exercise all the function calls that a
        # unit test might not put to the test.
        self.patch_logger()
        self.patch(boot_resources, 'call_and_check').return_code = 0
        self.patch(UEFIBootMethod, 'install_bootloader')

        # Prepare a fake repository, storage directory, and configuration.
        storage = self.make_dir()
        image = make_image_spec()
        arch, subarch, release, label = image
        repo = self.make_simplestreams_repo(image)
        config = {
            'boot': {
                'storage': storage,
                'sources': [
                    {
                        'path': repo,
                        'selections': [
                            {
                                'release': release,
                                'arches': [arch],
                                'subarches': [subarch],
                                'labels': [label],
                            },
                            ],
                    },
                    ],
                },
            }
        args = self.make_args(
            config_file=self.make_file(
                'bootresources.yaml', contents=yaml.safe_dump(config)))

        # Run the import code.
        boot_resources.main(args)

        # Verify the reuslts.
        self.assertThat(os.path.join(storage, 'cache'), DirExists())
        current = os.path.join(storage, 'current')
        self.assertTrue(os.path.islink(current))
        self.assertThat(current, DirExists())
        self.assertThat(os.path.join(current, 'pxelinux.0'), FileExists())
        self.assertThat(os.path.join(current, 'maas.meta'), FileExists())
        self.assertThat(os.path.join(current, 'maas.tgt'), FileExists())
        self.assertThat(
            os.path.join(current, arch, subarch, release, label),
            DirExists())

        # Verify the contents of the "meta" file.
        with open(os.path.join(current, 'maas.meta'), 'rb') as meta_file:
            meta_data = json.load(meta_file)
        self.assertEqual([arch], meta_data.keys())
        self.assertEqual([subarch], meta_data[arch].keys())
        self.assertEqual(
            [release],
            meta_data[arch][subarch].keys())
        self.assertEqual(
            [label],
            meta_data[arch][subarch][release].keys())
        self.assertItemsEqual(
            ['content_id', 'path', 'product_name', 'version_name'],
            meta_data[arch][subarch][release][label].keys())

    def test_raises_ioerror_when_no_config_file_found(self):
        self.patch_logger()
        no_config = os.path.join(
            self.make_dir(), '%s.yaml' % factory.make_name('no-config'))
        self.assertRaises(
            boot_resources.NoConfigFile,
            boot_resources.main, self.make_args(config_file=no_config))

    def test_raises_non_ENOENT_IOErrors(self):
        # main() will raise a NoConfigFile error when it encounters an
        # ENOENT IOError, but will otherwise just re-raise the original
        # IOError.
        mock_load_from_cache = self.patch(BootConfig, 'load_from_cache')
        other_error = IOError(randint(errno.ENOENT + 1, 1000))
        mock_load_from_cache.side_effect = other_error
        self.patch_logger()
        raised_error = self.assertRaises(
            IOError,
            boot_resources.main, self.make_args())
        self.assertEqual(other_error, raised_error)
