# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `upgrade-cluster` command."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from argparse import ArgumentParser
from collections import namedtuple
from os import (
    listdir,
    makedirs,
    readlink,
    symlink,
    )
import os.path

from maastesting.factory import factory
from maastesting.matchers import (
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
from mock import (
    ANY,
    Mock,
    )
from provisioningserver import upgrade_cluster
from provisioningserver.config import Config
from provisioningserver.pxe.install_image import install_image
from provisioningserver.testing.config import ConfigFixture
from testtools.matchers import (
    DirExists,
    FileContains,
    FileExists,
    Not,
    StartsWith,
    )


class TestUpgradeCluster(MAASTestCase):
    """Tests for the `upgrade-cluster` command itself."""

    def run_command(self):
        parser = ArgumentParser()
        upgrade_cluster.add_arguments(parser)
        upgrade_cluster.run(parser.parse_args(()))

    def patch_upgrade_hooks(self, hooks=None):
        """Temporarily replace the upgrade hooks."""
        if hooks is None:
            hooks = []
        self.patch(upgrade_cluster, 'UPGRADE_HOOKS', hooks)

    def test_calls_hooks(self):
        upgrade_hook = Mock()
        self.patch_upgrade_hooks([upgrade_hook])
        self.run_command()
        self.assertThat(upgrade_hook, MockCalledOnceWith())

    def test_calls_hooks_in_order(self):
        calls = []

        # Define some hooks.  They will be run in the order in which they are
        # listed (not in the order in which they are defined, or alphabetical
        # order, or any other order).

        def last_hook():
            calls.append('last')

        def first_hook():
            calls.append('first')

        def middle_hook():
            calls.append('middle')

        self.patch_upgrade_hooks([first_hook, middle_hook, last_hook])
        self.run_command()
        self.assertEqual(['first', 'middle', 'last'], calls)


class TestHookAddLabelDirectoryLevelToBootImages(MAASTestCase):
    """Tests for the `add_label_directory_level_to_boot_images` upgrade."""

    # The elements that go into a full image name.
    ImageElements = namedtuple(
        'ImageElements', ['arch', 'subarch', 'release', 'label', 'purpose'])

    def make_image_elements(self, label=None):
        """Create a full set of element names that go into an image name.

        :param label: Override for the `label` field.  Pass this to get a
            specific label, while keeping the other elements randomised.
        """
        fields = [
            factory.make_name(field)
            for field in self.ImageElements._fields
            ]
        if label is not None:
            [arch, subarch, release, _, purpose] = fields
            fields = [arch, subarch, release, label, purpose]
        return self.ImageElements(*fields)

    def substitute_purpose(self, elements, purpose):
        """Return a copy of `ImageElements`, but with different `purpose`."""
        return elements._replace(purpose=purpose)

    def make_tftproot_name(self):
        """Make up a tftp root name, but don't actually create it."""
        return '/' + factory.make_name('tftproot')

    def patch_tftp_root(self, tftproot=None):
        """Patch the TFTP root directory to a different location."""
        if tftproot is None:
            tftproot = self.make_dir()
        config = {'tftp': {'root': tftproot}}
        self.useFixture(ConfigFixture(config))
        return tftproot

    def compose_relative_legacy_path(self, elements):
        """Return a legacy image's path relative to TFTP root."""
        # Ignore the label field.
        arch, subarch, release, _, purpose = elements
        return os.path.join(arch, subarch, release, purpose)

    def compose_legacy_image_path(self, tftproot, elements):
        """Compose the full path for a pre-migration boot image.

        :param tftproot: Absolute path to TFTP root directory.
        :param elements: `ImageElements` describing an image.
        """
        self.assertThat(tftproot, StartsWith('/'))
        return os.path.join(
            tftproot, self.compose_relative_legacy_path(elements))

    def compose_modern_image_path(self, tftproot, elements):
        """Compose the full path for a post-migration boot image.

        :param tftproot: Absolute path to TFTP root directory.
        :param elements: `ImageElements` describing an image.
        """
        self.assertThat(tftproot, StartsWith('/'))
        self.assertIsNotNone(elements.label)
        return os.path.join(tftproot, *elements)

    def create_image(self, path):
        """Create a simulated boot image directory, with image files.

        The image directory will contain at least a file called `linux`.  For
        testing convenience it contains only randomised ASCII text.

        :param path: Full path to the image, i.e. including architecture,
            subarchitecture, etc.
        :return: Contents of the `linux` file, for test comparison later.
        """
        kernel_content = factory.getRandomString()
        os.makedirs(path)
        factory.make_file(path, 'linux', contents=kernel_content)
        factory.make_file(path, 'initrd.gz')
        return kernel_content

    def test_make_image_elements_returns_suitable_names(self):
        # make_image_elements is very convenient, but any crossed wires there
        # could mess up lots of other tests.  Make sure it does exactly what
        # we expect.
        elements = self.make_image_elements()
        self.assertIsInstance(elements, self.ImageElements)
        self.assertEqual(
            (
                elements.arch,
                elements.subarch,
                elements.release,
                elements.label,
                elements.purpose,
            ),
            tuple(elements))
        self.assertThat(elements.arch, StartsWith('arch'))
        self.assertThat(elements.subarch, StartsWith('subarch'))
        self.assertThat(elements.release, StartsWith('release'))
        self.assertThat(elements.label, StartsWith('label'))
        self.assertThat(elements.purpose, StartsWith('purpose'))

    def test_make_image_elements_overrides_label(self):
        label = factory.make_name('mylabel')
        elements = self.make_image_elements(label=label)
        self.assertThat(elements.arch, StartsWith('arch'))
        self.assertThat(elements.subarch, StartsWith('subarch'))
        self.assertThat(elements.release, StartsWith('release'))
        self.assertEqual(label, elements.label)
        self.assertThat(elements.purpose, StartsWith('purpose'))

    def test_compose_legacy_image_path(self):
        tftproot = self.make_tftproot_name()
        elements = self.make_image_elements()
        path = self.compose_legacy_image_path(tftproot, elements)
        self.assertEqual(
            os.path.join(
                tftproot, elements.arch, elements.subarch, elements.release,
                elements.purpose),
            path)
        self.assertNotIn(elements.label, path)
        self.assertNotEqual(
            self.compose_modern_image_path(tftproot, elements),
            path)

    def test_compose_modern_image_path(self):
        tftproot = self.make_tftproot_name()
        elements = self.make_image_elements()
        path = self.compose_modern_image_path(tftproot, elements)
        self.assertEqual(
            os.path.join(
                tftproot, elements.arch, elements.subarch, elements.release,
                elements.label, elements.purpose),
            path)

    def test_test_helpers_match_actual_code(self):
        # The helpers are consistent with themselves and with the
        # post-migration code, to the point where we can use them to create a
        # legacy image in the TFTP tree; locate it; use the real code to
        # install it into its modern location; and locate it there.
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements()
        old_path = self.compose_legacy_image_path(tftproot, elements)
        new_path = self.compose_modern_image_path(tftproot, elements)

        self.create_image(old_path)
        install_image(old_path, **elements._asdict())

        self.assertThat(new_path, DirExists())
        self.assertThat(os.path.join(new_path, 'linux'), FileExists())

    def test_list_dirs_lists_directories(self):
        parent = self.make_dir()
        subdir = factory.make_name('subdir')
        os.makedirs(os.path.join(parent, subdir))
        self.assertEqual(
            [os.path.join(parent, subdir)],
            upgrade_cluster.list_dirs(parent))

    def test_list_dirs_ignores_files(self):
        parent = self.make_dir()
        subfile = factory.make_name('file')
        factory.make_file(parent, subfile)
        self.assertEqual([], upgrade_cluster.list_dirs(parent))

    def test_list_dirs_includes_symlinks_to_dirs(self):
        parent = self.make_dir()
        subdir = factory.make_name('subdir')
        os.makedirs(os.path.join(parent, subdir))
        sublink = factory.make_name('sublink')
        os.symlink(subdir, os.path.join(parent, sublink))
        self.assertItemsEqual(
            [os.path.join(parent, subdir), os.path.join(parent, sublink)],
            upgrade_cluster.list_dirs(parent))

    def test_list_dirs_ignores_symlinks_to_files(self):
        parent = self.make_dir()
        subfile = factory.make_name('file')
        factory.make_file(parent, subfile)
        sublink = factory.make_name('sublink')
        os.symlink(subfile, os.path.join(parent, sublink))
        self.assertEqual([], upgrade_cluster.list_dirs(parent))

    def test_gather_legacy_images_finds_legacy_image(self):
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements()
        self.create_image(self.compose_legacy_image_path(tftproot, elements))
        self.assertEqual(
            [self.compose_relative_legacy_path(elements)],
            upgrade_cluster.gather_legacy_images(tftproot))

    def test_gather_legacy_images_ignores_modern_image(self):
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements()
        self.create_image(self.compose_modern_image_path(tftproot, elements))
        self.assertEqual([], upgrade_cluster.gather_legacy_images(tftproot))

    def test_gather_legacy_images_finds_relative_symlink_image(self):
        tftproot = self.patch_tftp_root()
        real_elements = self.make_image_elements()
        alt_purpose = factory.make_name('alt-purpose')
        linked_elements = self.substitute_purpose(real_elements, alt_purpose)
        real_image = self.compose_legacy_image_path(tftproot, real_elements)
        linked_image = self.compose_legacy_image_path(
            tftproot, linked_elements)
        self.create_image(real_image)
        symlink(real_elements.purpose, linked_image)

        self.assertItemsEqual(
            [
                self.compose_relative_legacy_path(real_elements),
                self.compose_relative_legacy_path(linked_elements),
            ],
            upgrade_cluster.gather_legacy_images(tftproot))

    def test_gather_legacy_images_finds_absolute_symlink_image(self):
        tftproot = self.patch_tftp_root()
        real_elements = self.make_image_elements()
        alt_purpose = factory.make_name('alt-purpose')
        linked_elements = self.substitute_purpose(real_elements, alt_purpose)
        real_image = self.compose_legacy_image_path(tftproot, real_elements)
        linked_image = self.compose_legacy_image_path(
            tftproot, linked_elements)
        self.create_image(real_image)
        symlink(real_image, linked_image)

        self.assertItemsEqual(
            [
                self.compose_relative_legacy_path(real_elements),
                self.compose_relative_legacy_path(linked_elements),
            ],
            upgrade_cluster.gather_legacy_images(tftproot))

    def test_move_real_boot_image_moves_legacy_image_directory(self):
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements(label='release')
        legacy_image = self.compose_legacy_image_path(tftproot, elements)
        modern_image = self.compose_modern_image_path(tftproot, elements)
        kernel_content = self.create_image(legacy_image)

        upgrade_cluster.move_real_boot_image(
            tftproot, self.compose_relative_legacy_path(elements))

        self.assertThat(legacy_image, Not(DirExists()))
        self.assertThat(modern_image, DirExists())
        self.assertThat(
            os.path.join(modern_image, 'linux'),
            FileContains(kernel_content))

    def test_move_real_boot_image_deletes_if_modern_image_exists(self):
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements(label='release')
        modern_image = self.compose_modern_image_path(tftproot, elements)
        legacy_image = self.compose_legacy_image_path(tftproot, elements)
        modern_kernel_content = self.create_image(modern_image)
        self.create_image(legacy_image)

        upgrade_cluster.move_real_boot_image(
            tftproot, self.compose_relative_legacy_path(elements))

        self.assertThat(modern_image, DirExists())
        self.assertThat(legacy_image, Not(DirExists()))
        self.assertThat(
            os.path.join(modern_image, 'linux'),
            FileContains(modern_kernel_content))

    def test_move_linked_boot_image_moves_relative_link(self):
        tftproot = self.patch_tftp_root()
        real_elements = self.make_image_elements(label='release')
        alt_purpose = factory.make_name('alt-purpose')
        linked_elements = self.substitute_purpose(real_elements, alt_purpose)
        legacy_real_image = self.compose_legacy_image_path(
            tftproot, real_elements)
        legacy_linked_image = self.compose_legacy_image_path(
            tftproot, linked_elements)
        modern_real_image = self.compose_modern_image_path(
            tftproot, real_elements)
        modern_linked_image = self.compose_modern_image_path(
            tftproot, linked_elements)
        self.create_image(legacy_real_image)
        symlink(real_elements.purpose, legacy_linked_image)

        upgrade_cluster.move_linked_boot_image(
            tftproot, self.compose_relative_legacy_path(linked_elements))

        # The new link is either absolute or relative; we don't care, as long
        # as it points at the "modern" image.
        self.assertIn(
            readlink(modern_linked_image),
            {modern_real_image, real_elements.purpose})

    def test_move_linked_boot_image_reconstitutes_absolute_link(self):
        tftproot = self.patch_tftp_root()
        real_elements = self.make_image_elements(label='release')
        alt_purpose = factory.make_name('alt-purpose')
        linked_elements = self.substitute_purpose(real_elements, alt_purpose)
        legacy_real_image = self.compose_legacy_image_path(
            tftproot, real_elements)
        legacy_linked_image = self.compose_legacy_image_path(
            tftproot, linked_elements)
        modern_real_image = self.compose_modern_image_path(
            tftproot, real_elements)
        modern_linked_image = self.compose_modern_image_path(
            tftproot, linked_elements)
        self.create_image(legacy_real_image)
        symlink(legacy_real_image, legacy_linked_image)

        upgrade_cluster.move_linked_boot_image(
            tftproot, self.compose_relative_legacy_path(linked_elements))

        self.assertEqual(
            modern_real_image,
            readlink(modern_linked_image))

    def test_move_linked_boot_image_moves_external_link(self):
        real_image = os.path.join(self.make_dir(), factory.make_name('image'))
        kernel_content = self.create_image(real_image)
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements(label='release')
        legacy_linked_image = self.compose_legacy_image_path(
            tftproot, elements)
        makedirs(os.path.dirname(legacy_linked_image))
        modern_linked_image = self.compose_modern_image_path(
            tftproot, elements)
        symlink(real_image, legacy_linked_image)

        upgrade_cluster.move_linked_boot_image(
            tftproot, self.compose_relative_legacy_path(elements))

        self.assertEqual(real_image, readlink(modern_linked_image))
        self.assertThat(
            os.path.join(modern_linked_image, 'linux'),
            FileContains(kernel_content))

    def test_move_linked_boot_image_deletes_if_modern_image_exists(self):
        tftproot = self.patch_tftp_root()
        real_elements = self.make_image_elements(label='release')
        alt_purpose = factory.make_name('alt-purpose')
        linked_elements = self.substitute_purpose(real_elements, alt_purpose)
        legacy_real_image = self.compose_legacy_image_path(
            tftproot, real_elements)
        legacy_linked_image = self.compose_legacy_image_path(
            tftproot, linked_elements)
        modern_real_image = self.compose_modern_image_path(
            tftproot, real_elements)
        modern_linked_image = self.compose_modern_image_path(
            tftproot, linked_elements)
        self.create_image(legacy_real_image)
        modern_kernel_content = self.create_image(modern_real_image)
        symlink(legacy_real_image, legacy_linked_image)
        upgrade_cluster.move_real_boot_image(
            tftproot, self.compose_relative_legacy_path(real_elements))

        upgrade_cluster.move_linked_boot_image(
            tftproot, self.compose_relative_legacy_path(linked_elements))

        self.assertThat(
            os.path.join(modern_real_image, 'linux'),
            FileContains(modern_kernel_content))
        self.assertThat(
            os.path.join(modern_linked_image, 'linux'),
            FileContains(modern_kernel_content))
        self.assertThat(legacy_linked_image, Not(FileExists()))
        self.assertThat(legacy_linked_image, Not(DirExists()))

    def test_hook_does_nothing_if_images_directory_does_not_exist(self):
        tftproot = os.path.join(self.make_dir(), factory.make_name('tftp'))
        self.patch_tftp_root(tftproot)
        upgrade_cluster.add_label_directory_level_to_boot_images()
        self.assertThat(tftproot, Not(DirExists()))

    def test_hook_does_nothing_if_images_directory_is_empty(self):
        tftproot = self.patch_tftp_root()
        upgrade_cluster.add_label_directory_level_to_boot_images()
        self.assertEqual([], listdir(tftproot))

    def test_hook_does_nothing_if_no_upgrade_needed(self):
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements()
        new_path = self.compose_modern_image_path(tftproot, elements)
        self.create_image(new_path)
        upgrade_cluster.add_label_directory_level_to_boot_images()
        self.assertThat(os.path.join(new_path, 'linux'), FileExists())

    def test_hook_renames_labelless_image_to_use_release_label(self):
        tftproot = self.patch_tftp_root()
        # The old path does not include the label, but in the new path it will
        # be "release".
        elements = self.make_image_elements(label='release')
        old_path = self.compose_legacy_image_path(tftproot, elements)
        self.create_image(old_path)
        new_path = self.compose_modern_image_path(tftproot, elements)

        upgrade_cluster.add_label_directory_level_to_boot_images()

        self.assertThat(new_path, DirExists())
        self.assertThat(os.path.join(new_path, 'linux'), FileExists())
        self.assertThat(old_path, Not(DirExists()))

    def test_hook_renames_symlinked_image(self):
        tftproot = self.patch_tftp_root()
        elements = self.make_image_elements(label='release')
        alt_purpose = factory.make_name('alt-purpose')
        legacy_real_path = self.compose_legacy_image_path(tftproot, elements)
        legacy_linked_path = os.path.join(
            os.path.dirname(legacy_real_path), alt_purpose)
        self.create_image(legacy_real_path)
        modern_real_path = self.compose_modern_image_path(tftproot, elements)
        modern_linked_path = os.path.join(
            os.path.dirname(modern_real_path), alt_purpose)
        symlink(legacy_real_path, legacy_linked_path)
        self.assertThat(legacy_linked_path, DirExists())

        upgrade_cluster.add_label_directory_level_to_boot_images()

        self.assertThat(legacy_linked_path, Not(FileExists()))
        self.assertEqual(modern_real_path, readlink(modern_linked_path))

    def test_hook_merges_different_old_and_new_images_with_same_label(self):
        tftproot = self.patch_tftp_root()
        modern_elements = self.make_image_elements(label='release')
        legacy_image_purpose = factory.make_name('legacy-purpose')
        legacy_elements = self.substitute_purpose(
            modern_elements, legacy_image_purpose)
        modern_image = self.compose_modern_image_path(
            tftproot, modern_elements)
        legacy_image = self.compose_legacy_image_path(
            tftproot, legacy_elements)
        self.create_image(modern_image)
        self.create_image(legacy_image)

        upgrade_cluster.add_label_directory_level_to_boot_images()

        self.assertThat(modern_image, DirExists())
        self.assertThat(legacy_image, Not(DirExists()))
        self.assertThat(
            self.compose_modern_image_path(tftproot, legacy_elements),
            DirExists())

    def test_hook_migrates_relative_symlinked_image(self):
        # Some images are really just symlinks to similar images but with a
        # different "boot purpose" name.  These must also be migrated.
        # This tests checks that for links with relative paths.
        tftproot = self.patch_tftp_root()
        real_image_elements = self.make_image_elements(label='release')
        alt_purpose = factory.make_name('alt-purpose')
        linked_image_elements = self.substitute_purpose(
            real_image_elements, alt_purpose)
        real_legacy_image = self.compose_legacy_image_path(
            tftproot, real_image_elements)
        kernel_content = self.create_image(real_legacy_image)
        linked_legacy_image = self.compose_legacy_image_path(
            tftproot, linked_image_elements)
        linked_modern_image = self.compose_modern_image_path(
            tftproot, linked_image_elements)
        symlink(real_image_elements.purpose, linked_legacy_image)

        upgrade_cluster.add_label_directory_level_to_boot_images()

        self.assertThat(linked_modern_image, DirExists())
        self.assertThat(linked_legacy_image, Not(DirExists()))
        self.assertThat(linked_legacy_image, Not(FileExists()))
        self.assertThat(
            os.path.join(linked_modern_image, 'linux'),
            FileContains(kernel_content))

    def test_hook_migrates_absolute_symlinked_image(self):
        # Some images are really just symlinks to similar images but with a
        # different "boot purpose" name.  These must also be migrated.
        # This tests checks that for links with absolute paths.
        tftproot = self.patch_tftp_root()
        real_image_elements = self.make_image_elements(label='release')
        alt_purpose = factory.make_name('alt-purpose')
        linked_image_elements = self.substitute_purpose(
            real_image_elements, alt_purpose)
        real_legacy_image = self.compose_legacy_image_path(
            tftproot, real_image_elements)
        kernel_content = self.create_image(real_legacy_image)
        linked_legacy_image = self.compose_legacy_image_path(
            tftproot, linked_image_elements)
        linked_modern_image = self.compose_modern_image_path(
            tftproot, linked_image_elements)
        symlink(real_legacy_image, linked_legacy_image)

        upgrade_cluster.add_label_directory_level_to_boot_images()

        self.assertThat(linked_modern_image, DirExists())
        self.assertThat(linked_legacy_image, Not(DirExists()))
        self.assertThat(linked_legacy_image, Not(FileExists()))
        self.assertThat(
            os.path.join(linked_modern_image, 'linux'),
            FileContains(kernel_content))

    def test_hook_ignores_non_image_entries(self):
        tftproot = self.patch_tftp_root()
        factory.make_file(tftproot)
        os.makedirs(os.path.join(tftproot, 'noarch', 'nosub', 'norelease'))
        entries_before = listdir(tftproot)
        upgrade_cluster.add_label_directory_level_to_boot_images()
        self.assertItemsEqual(entries_before, listdir(tftproot))


class TestGenerateBootResourcesConfig(MAASTestCase):
    """Tests for the `generate_boot_resources_config` upgrade."""

    def patch_rewrite_boot_resources_config(self):
        """Patch `rewrite_boot_resources_config` with a mock."""
        return self.patch(upgrade_cluster, 'rewrite_boot_resources_config')

    def patch_config(self, config):
        """Patch the `bootresources.yaml` config with a given dict."""
        original_load = Config.load_from_cache

        @classmethod
        def fake_config_load(cls, filename=None):
            """Fake `Config.load_from_cache`.

            Returns a susbtitute for `bootresources.yaml`, but defers to the
            original implementation for other files.  This means we can still
            patch the original, and it means we'll probably get a tell-tale
            error if any code underneath the tests accidentally tries to
            load pserv.yaml.
            """
            if os.path.basename(filename) == 'bootresources.yaml':
                return config
            else:
                return original_load(Config, filename=filename)

        self.patch(Config, 'load_from_cache', fake_config_load)

    def test_does_nothing_if_configure_me_is_False(self):
        self.patch_config({'boot': {'configure_me': False}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockNotCalled())

    def test_does_nothing_if_configure_me_is_missing(self):
        self.patch_config({'boot': {}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockNotCalled())

    def test_rewrites_if_configure_me_is_True(self):
        self.patch_config({'boot': {'configure_me': True}})
        rewrite_config = self.patch_rewrite_boot_resources_config()
        upgrade_cluster.generate_boot_resources_config()
        self.assertThat(rewrite_config, MockCalledOnceWith(ANY))
