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
from subprocess import Popen, PIPE
from testtools.content import Content
from testtools.content_type import UTF8_TEXT

from maastesting.factory import factory
from maastesting.matchers import MockCalledOnceWith
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver.boot.uefi import UEFIBootMethod
from provisioningserver.config import BootConfig
from provisioningserver.import_images import boot_resources
from provisioningserver.utils import write_text_file
from simplestreams.util import SignatureMissingException
from testtools.matchers import (
    DirExists,
    FileExists,
    )
import yaml


def make_image_spec():
    """Return an `ImageSpec` with random values."""
    return boot_resources.ImageSpec(
        factory.make_name('arch'),
        factory.make_name('subarch'),
        factory.make_name('release'),
        factory.make_name('label'),
        )


class TestBootImageMapping(MAASTestCase):
    """Tests for `BootImageMapping`."""

    def test_initially_empty(self):
        self.assertItemsEqual([], boot_resources.BootImageMapping().items())

    def test_items_returns_items(self):
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict = set_resource(image_spec=image, resource=resource)
        self.assertItemsEqual([(image, resource)], image_dict.items())

    def test_setdefault_sets_unset_item(self):
        image_dict = boot_resources.BootImageMapping()
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict.setdefault(image, resource)
        self.assertItemsEqual([(image, resource)], image_dict.items())

    def test_setdefault_leaves_set_item_unchanged(self):
        image = make_image_spec()
        old_resource = factory.make_name('resource')
        image_dict = set_resource(image_spec=image, resource=old_resource)
        image_dict.setdefault(image, factory.make_name('newresource'))
        self.assertItemsEqual([(image, old_resource)], image_dict.items())

    def test_dump_json_is_consistent(self):
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict_1 = set_resource(image_spec=image, resource=resource)
        image_dict_2 = set_resource(image_spec=image, resource=resource)
        self.assertEqual(image_dict_1.dump_json(), image_dict_2.dump_json())

    def test_dump_json_represents_empty_dict_as_empty_object(self):
        self.assertEqual('{}', boot_resources.BootImageMapping().dump_json())

    def test_dump_json_represents_entry(self):
        image = make_image_spec()
        resource = factory.make_name('resource')
        image_dict = set_resource(image_spec=image, resource=resource)
        self.assertEqual(
            {
                image.arch: {
                    image.subarch: {
                        image.release: {image.label: resource},
                    },
                },
            },
            json.loads(image_dict.dump_json()))

    def test_dump_json_combines_similar_entries(self):
        image = make_image_spec()
        other_release = factory.make_name('other-release')
        resource1 = factory.make_name('resource')
        resource2 = factory.make_name('other-resource')
        image_dict = boot_resources.BootImageMapping()
        set_resource(image_dict, image, resource1)
        set_resource(
            image_dict, image._replace(release=other_release), resource2)
        self.assertEqual(
            {
                image.arch: {
                    image.subarch: {
                        image.release: {image.label: resource1},
                        other_release: {image.label: resource2},
                    },
                },
            },
            json.loads(image_dict.dump_json()))


class TestValuePassesFilterList(MAASTestCase):
    """Tests for `value_passes_filter_list`."""

    def test_nothing_passes_empty_list(self):
        self.assertFalse(
            boot_resources.value_passes_filter_list(
                [], factory.make_name('value')))

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            boot_resources.value_passes_filter_list(
                [factory.make_name('filter')], factory.make_name('value')))

    def test_matched_value_passes(self):
        value = factory.make_name('value')
        self.assertTrue(
            boot_resources.value_passes_filter_list([value], value))

    def test_value_passes_if_matched_anywhere_in_filter(self):
        value = factory.make_name('value')
        self.assertTrue(
            boot_resources.value_passes_filter_list(
                [
                    factory.make_name('filter'),
                    value,
                    factory.make_name('filter'),
                ],
                value))

    def test_any_value_passes_asterisk(self):
        self.assertTrue(
            boot_resources.value_passes_filter_list(
                ['*'], factory.make_name('value')))


class TestValuePassesFilter(MAASTestCase):
    """Tests for `value_passes_filter`."""

    def test_unmatched_value_does_not_pass(self):
        self.assertFalse(
            boot_resources.value_passes_filter(
                factory.make_name('filter'), factory.make_name('value')))

    def test_matching_value_passes(self):
        value = factory.make_name('value')
        self.assertTrue(boot_resources.value_passes_filter(value, value))

    def test_any_value_matches_asterisk(self):
        self.assertTrue(
            boot_resources.value_passes_filter(
                '*', factory.make_name('value')))


def make_boot_resource():
    """Create a fake resource dict."""
    return {
        'content_id': factory.make_name('content_id'),
        'product_name': factory.make_name('product_name'),
        'version_name': factory.make_name('version_name'),
        }


class TestProductMapping(MAASTestCase):
    """Tests for `ProductMapping`."""

    def test_initially_empty(self):
        self.assertEqual({}, boot_resources.ProductMapping().mapping)

    def test_make_key_extracts_identifying_items(self):
        resource = make_boot_resource()
        content_id = resource['content_id']
        product_name = resource['product_name']
        version_name = resource['version_name']
        self.assertEqual(
            (content_id, product_name, version_name),
            boot_resources.ProductMapping.make_key(resource))

    def test_make_key_ignores_other_items(self):
        resource = make_boot_resource()
        resource['other_item'] = factory.make_name('other')
        self.assertEqual(
            (
                resource['content_id'],
                resource['product_name'],
                resource['version_name'],
            ),
            boot_resources.ProductMapping.make_key(resource))

    def test_make_key_fails_if_key_missing(self):
        resource = make_boot_resource()
        del resource['version_name']
        self.assertRaises(
            KeyError,
            boot_resources.ProductMapping.make_key, resource)

    def test_add_creates_subarches_list_if_needed(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        self.assertEqual(
            {product_dict.make_key(resource): [subarch]},
            product_dict.mapping)

    def test_add_appends_to_existing_list(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarches = [factory.make_name('subarch') for _ in range(2)]
        for subarch in subarches:
            product_dict.add(resource, subarch)
        self.assertEqual(
            {product_dict.make_key(resource): subarches},
            product_dict.mapping)

    def test_contains_returns_true_for_stored_item(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        self.assertTrue(product_dict.contains(resource))

    def test_contains_returns_false_for_unstored_item(self):
        self.assertFalse(
            boot_resources.ProductMapping().contains(make_boot_resource()))

    def test_contains_ignores_similar_items(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource.copy(), subarch)
        resource['product_name'] = factory.make_name('other')
        self.assertFalse(product_dict.contains(resource))

    def test_contains_ignores_extraneous_keys(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource.copy(), subarch)
        resource['other_item'] = factory.make_name('other')
        self.assertTrue(product_dict.contains(resource))

    def test_get_returns_stored_item(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        self.assertEqual([subarch], product_dict.get(resource))

    def test_get_fails_for_unstored_item(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource.copy(), subarch)
        resource['content_id'] = factory.make_name('other')
        self.assertRaises(KeyError, product_dict.get, resource)

    def test_get_ignores_extraneous_keys(self):
        product_dict = boot_resources.ProductMapping()
        resource = make_boot_resource()
        subarch = factory.make_name('subarch')
        product_dict.add(resource, subarch)
        resource['other_item'] = factory.make_name('other')
        self.assertEqual([subarch], product_dict.get(resource))


class TestBootReverse(MAASTestCase):
    """Tests for `boot_reverse`."""

    def test_maps_empty_dict_to_empty_dict(self):
        empty_boot_image_dict = boot_resources.BootImageMapping()
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
        boot_dict = boot_resources.BootImageMapping()
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


class TestImagePassesFilter(MAASTestCase):
    """Tests for `image_passes_filter`."""

    def make_filter_from_image(self, image_spec=None):
        """Create a filter dict that matches the given `ImageSpec`.

        If `image_spec` is not given, creates a random value.
        """
        if image_spec is None:
            image_spec = make_image_spec()
        return {
            'arches': [image_spec.arch],
            'subarches': [image_spec.subarch],
            'release': image_spec.release,
            'labels': [image_spec.label],
            }

    def test_any_image_passes_none_filter(self):
        arch, subarch, release, label = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                None, arch, subarch, release, label))

    def test_any_image_passes_empty_filter(self):
        arch, subarch, release, label = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                [], arch, subarch, release, label))

    def test_image_passes_matching_filter(self):
        image = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                [self.make_filter_from_image(image)],
                image.arch, image.subarch, image.release, image.label))

    def test_image_does_not_pass_nonmatching_filter(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [self.make_filter_from_image()],
                image.arch, image.subarch, image.release, image.label))

    def test_image_passes_if_one_filter_matches(self):
        image = make_image_spec()
        self.assertTrue(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(),
                    self.make_filter_from_image(image),
                    self.make_filter_from_image(),
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_release(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        release=factory.make_name('other-release')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_arches(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        arch=factory.make_name('other-arch')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_subarches(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        subarch=factory.make_name('other-subarch')))
                ], image.arch, image.subarch, image.release, image.label))

    def test_filter_checks_labels(self):
        image = make_image_spec()
        self.assertFalse(
            boot_resources.image_passes_filter(
                [
                    self.make_filter_from_image(image._replace(
                        label=factory.make_name('other-label')))
                ], image.arch, image.subarch, image.release, image.label))


def set_resource(boot_dict=None, image_spec=None, resource=None):
    """Add boot resource to a `BootImageMapping`, creating it if necessary."""
    if boot_dict is None:
        boot_dict = boot_resources.BootImageMapping()
    if image_spec is None:
        image_spec = make_image_spec()
    if resource is None:
        resource = factory.make_name('boot-resource')
    boot_dict.mapping[image_spec] = resource
    return boot_dict


class TestBootMerge(MAASTestCase):
    """Tests for `boot_merge`."""

    def test_integrates(self):
        # End-to-end scenario for boot_merge: start with an empty boot
        # resources dict, and receive one resource from Simplestreams.
        total_resources = boot_resources.BootImageMapping()
        resources_from_repo = set_resource()
        boot_resources.boot_merge(total_resources, resources_from_repo)
        # Since we started with an empty dict, the result contains the same
        # item that we got from Simplestreams, and nothing else.
        self.assertEqual(resources_from_repo.mapping, total_resources.mapping)

    def test_obeys_filters(self):
        filters = [
            {
                'arches': [factory.make_name('other-arch')],
                'subarches': [factory.make_name('other-subarch')],
                'release': factory.make_name('other-release'),
                'label': [factory.make_name('other-label')],
            },
            ]
        total_resources = boot_resources.BootImageMapping()
        resources_from_repo = set_resource()
        boot_resources.boot_merge(
            total_resources, resources_from_repo, filters=filters)
        self.assertEqual({}, total_resources.mapping)

    def test_does_not_overwrite_existing_entry(self):
        image = make_image_spec()
        total_resources = set_resource(
            resource="Original resource", image_spec=image)
        original_resources = total_resources.mapping.copy()
        resources_from_repo = set_resource(
            resource="New resource", image_spec=image)
        boot_resources.boot_merge(total_resources, resources_from_repo)
        self.assertEqual(original_resources, total_resources.mapping)


class TestGetSigningPolicy(MAASTestCase):
    """Tests for `get_signing_policy`."""

    def test_picks_nonchecking_policy_for_json_index(self):
        path = 'streams/v1/index.json'
        policy = boot_resources.get_signing_policy(path)
        content = factory.getRandomString()
        self.assertEqual(
            content,
            policy(content, path, factory.make_name('keyring')))

    def test_picks_checking_policy_for_sjson_index(self):
        path = 'streams/v1/index.sjson'
        content = factory.getRandomString()
        policy = boot_resources.get_signing_policy(path)
        self.assertRaises(
            SignatureMissingException,
            policy, content, path, factory.make_name('keyring'))

    def test_picks_checking_policy_for_json_gpg_index(self):
        path = 'streams/v1/index.json.gpg'
        content = factory.getRandomString()
        policy = boot_resources.get_signing_policy(path)
        self.assertRaises(
            SignatureMissingException,
            policy, content, path, factory.make_name('keyring'))

    def test_injects_default_keyring_if_passed(self):
        path = 'streams/v1/index.json.gpg'
        content = factory.getRandomString()
        keyring = factory.make_name('keyring')
        self.patch(boot_resources, 'policy_read_signed')
        policy = boot_resources.get_signing_policy(path, keyring)
        policy(content, path)
        self.assertThat(
            boot_resources.policy_read_signed,
            MockCalledOnceWith(mock.ANY, mock.ANY, keyring=keyring))


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
