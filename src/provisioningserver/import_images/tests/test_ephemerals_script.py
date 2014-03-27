# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for `ephemerals_script`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

from os import (
    listdir,
    readlink,
    )
import os.path
import subprocess

from maastesting.factory import factory
from provisioningserver.import_images import ephemerals_script
from provisioningserver.import_images.ephemerals_script import (
    compose_filter,
    create_symlinked_image_dir,
    extract_image_tarball,
    install_image_from_simplestreams,
    move_file_by_glob,
    )
from provisioningserver.pxe.tftppath import (
    compose_image_path,
    locate_tftp_path,
    )
from provisioningserver.testing.config import ConfigFixture
from provisioningserver.testing.testcase import PservTestCase
from provisioningserver.utils import (
    ExternalProcessError,
    read_text_file,
    )
from testtools.matchers import (
    FileContains,
    FileExists,
    Not,
    StartsWith,
    )


def split_path(path):
    """Return directory and filename component of a file path."""
    return os.path.dirname(path), os.path.basename(path)


class TestHelpers(PservTestCase):
    def make_target(self):
        """Return an existing directory, and nonexistent filename."""
        return self.make_dir(), factory.make_name()

    def test_move_file_by_glob_moves_file(self):
        content = factory.getRandomString()
        source_dir, source_name = split_path(self.make_file(contents=content))
        target_dir, target_name = self.make_target()

        move_file_by_glob(
            source_dir, source_name[:3] + '*',
            target_dir, target_name)

        self.assertThat(
            os.path.join(source_dir, source_name),
            Not(FileExists()))
        self.assertThat(
            os.path.join(target_dir, target_name),
            FileContains(content))

    def test_move_file_by_glob_returns_target_path(self):
        source_dir, source_name = split_path(self.make_file())
        target_dir, target_name = self.make_target()

        target = move_file_by_glob(
            source_dir, source_name, target_dir, target_name)

        self.assertEqual(os.path.join(target_dir, target_name), target)

    def test_move_file_by_glob_ignores_nonmatching_files(self):
        content = factory.getRandomString()
        source_dir, source_name = split_path(self.make_file(contents=content))
        other_content = factory.getRandomString()
        other_file = factory.make_file(source_dir, contents=other_content)
        target_dir, target_name = self.make_target()

        move_file_by_glob(source_dir, source_name, target_dir, target_name)

        self.assertThat(other_file, FileContains(other_content))
        self.assertThat(
            os.path.join(target_dir, target_name),
            FileContains(content))
        self.assertItemsEqual(
            [os.path.basename(other_file)],
            os.listdir(source_dir))
        self.assertItemsEqual([target_name], os.listdir(target_dir))

    def test_move_file_by_glob_fails_if_no_files_match(self):
        self.assertRaises(
            AssertionError,
            move_file_by_glob,
            self.make_dir(), factory.make_name() + '*',
            self.make_dir(), factory.make_name())

    def test_move_file_by_glob_fails_if_multiple_files_match(self):
        source_dir = self.make_dir()
        factory.make_file(source_dir)
        factory.make_file(source_dir)

        self.assertRaises(
            AssertionError,
            move_file_by_glob,
            source_dir, '*', self.make_dir(), factory.make_name())

    def test_compose_filter_returns_single_literal(self):
        key = factory.make_name('key')
        literal = factory.getRandomString()
        self.assertEqual(
            '%s~(%s)' % (key, literal),
            compose_filter(key, [literal]))

    def test_compose_filter_combines_literals(self):
        key = factory.make_name('key')
        values = (factory.getRandomString(), factory.getRandomString())
        self.assertEqual(
            '%s~(%s|%s)' % (key, values[0], values[1]),
            compose_filter(key, values))

    def test_compose_filter_escapes_literals_for_regex_use(self):
        key = factory.make_name('key')
        self.assertEqual(
            '%s~(x\\.y\\*)' % key,
            compose_filter(key, ['x.y*']))


class TestExtractImageTarball(PservTestCase):
    """Tests for `extract_image_tarball`."""

    def test_copies_boot_image_files_from_tarball(self):
        prefix = factory.make_name()
        kernel_content = factory.getRandomString()
        initrd_content = factory.getRandomString()
        img_content = factory.getRandomString()
        tarball = factory.make_tarball(self.make_dir(), {
            '%s-vmlinuz.gz' % prefix: kernel_content,
            '%s-initrd.gz' % prefix: initrd_content,
            '%s.img' % prefix: img_content,
            })
        target_dir = self.make_dir()
        self.patch(ephemerals_script, 'call_uec2roottar')

        extract_image_tarball(tarball, target_dir)

        self.assertItemsEqual(
            ['linux', 'initrd.gz', 'disk.img'],
            listdir(target_dir))
        self.assertThat(
            os.path.join(target_dir, 'linux'),
            FileContains(kernel_content))
        self.assertThat(
            os.path.join(target_dir, 'initrd.gz'),
            FileContains(initrd_content))
        self.assertThat(
            os.path.join(target_dir, 'disk.img'),
            FileContains(img_content))

    def test_ignores_extraneous_files_in_tarball(self):
        prefix = factory.make_name()
        tarball = factory.make_tarball(self.make_dir(), {
            '%s-vmlinuz.gz' % prefix: None,
            '%s-initrd.gz' % prefix: None,
            '%s.img' % prefix: None,
            'HELLO.TXT': None,
            })
        target_dir = self.make_dir()
        self.patch(ephemerals_script, 'call_uec2roottar')

        extract_image_tarball(tarball, target_dir)

        self.assertItemsEqual(
            ['linux', 'initrd.gz', 'disk.img'],
            listdir(target_dir))

    def test_runs_uec2roottar(self):
        check_call = self.patch(subprocess, 'check_call')
        fake_image = factory.make_name('image')
        self.patch(ephemerals_script, 'move_file_by_glob').return_value = (
            fake_image)
        tarball = factory.make_name('tarball') + '.tar.gz'
        target_dir = self.make_dir()

        extract_image_tarball(tarball, target_dir)

        check_call.assert_called_with([
            'uec2roottar',
            fake_image,
            os.path.join(target_dir, 'dist-root.tar.gz'),
            ])

    def test_cleans_up_temp_location(self):
        self.patch(subprocess, 'check_call')
        fake_image = factory.make_name('image')
        self.patch(ephemerals_script, 'move_file_by_glob').return_value = (
            fake_image)
        tarball = factory.make_name('tarball') + '.tar.gz'
        target_dir = self.make_dir()
        temp_location = self.make_dir()

        extract_image_tarball(tarball, target_dir, temp_location)

        self.assertItemsEqual([], listdir(temp_location))

    def test_cleans_up_after_failure(self):
        self.patch(subprocess, 'check_call').side_effect = (
            ExternalProcessError(-1, "some_command"))
        fake_image = factory.make_name('image')
        self.patch(ephemerals_script, 'move_file_by_glob').return_value = (
            fake_image)
        tarball = factory.make_name('tarball') + '.tar.gz'
        target_dir = self.make_dir()
        temp_location = self.make_dir()

        self.assertRaises(
            ExternalProcessError,
            extract_image_tarball, tarball, target_dir, temp_location)

        self.assertItemsEqual([], listdir(temp_location))


class TestCreateSymlinkedImageDir(PservTestCase):
    """Tests for `create_symlinked_image_dir`."""

    def make_original_dir(self):
        """Create a directory with the kernel, initrd and root tarball."""
        original_dir = self.make_dir()
        factory.make_file(original_dir, 'linux')
        factory.make_file(original_dir, 'initrd.gz')
        factory.make_file(original_dir, 'dist-root.tar.gz')
        return original_dir

    def test_symlinks_files(self):
        original_dir = self.make_original_dir()
        temp_location = self.make_dir()

        image_dir = create_symlinked_image_dir(original_dir, temp_location)

        self.assertNotEqual(original_dir, image_dir)
        self.assertNotEqual(temp_location, image_dir)
        self.assertThat(image_dir, StartsWith(temp_location + '/'))
        self.assertItemsEqual(
            ['linux', 'initrd.gz', 'root.tar.gz'],
            listdir(image_dir))
        self.assertEqual(
            os.path.join(original_dir, 'linux'),
            readlink(os.path.join(image_dir, 'linux')))
        self.assertEqual(
            os.path.join(original_dir, 'initrd.gz'),
            readlink(os.path.join(image_dir, 'initrd.gz')))
        self.assertEqual(
            os.path.join(original_dir, 'dist-root.tar.gz'),
            readlink(os.path.join(image_dir, 'root.tar.gz')))

    def test_cleans_up_temp_location(self):
        original_dir = self.make_original_dir()
        temp_location = self.make_dir()

        image_dir = create_symlinked_image_dir(original_dir, temp_location)

        # Nothing is left in temp_location except the result.
        self.assertItemsEqual(
            [os.path.basename(image_dir)],
            listdir(temp_location))

    def test_cleans_up_after_failure(self):
        class DeliberateFailure(RuntimeError):
            pass

        self.patch(ephemerals_script, 'symlink').side_effect = (
            DeliberateFailure("Symlinking intentionally broken"))
        original_dir = self.make_dir()
        temp_location = self.make_dir()

        self.assertRaises(
            DeliberateFailure,
            create_symlinked_image_dir, original_dir, temp_location)

        self.assertItemsEqual([], listdir(temp_location))


class TestInstallImageFromSimplestreams(PservTestCase):
    """Tests for `install_image_from_simplestreams`."""

    def prepare_storage_dir(self):
        """Set up a storage directory with kernel, initrd, and root tarball."""
        storage = self.make_dir()
        factory.make_file(storage, 'linux')
        factory.make_file(storage, 'initrd.gz')
        factory.make_file(storage, 'dist-root.tar.gz')
        return storage

    def patch_config(self, tftp_root):
        """Set up a fake config, pointing to the given TFTP root directory."""
        self.useFixture(ConfigFixture({'tftp': {'root': tftp_root}}))

    def test_installs_image(self):
        tftp_root = self.make_dir()
        self.patch_config(tftp_root)
        storage_dir = self.prepare_storage_dir()
        release = factory.make_name('release')
        label = factory.make_name('label')
        arch = factory.make_name('arch')

        install_image_from_simplestreams(
            storage_dir, release=release, label=label, arch=arch)

        install_dir = locate_tftp_path(
            compose_image_path(
                arch, 'generic', release, label, 'commissioning'),
            tftproot=tftp_root)
        self.assertItemsEqual(
            ['linux', 'initrd.gz', 'root.tar.gz'],
            listdir(install_dir))
        self.assertThat(
            os.path.join(install_dir, 'linux'),
            FileContains(read_text_file(os.path.join(storage_dir, 'linux'))))

    def test_cleans_up_temp_location(self):
        self.patch(ephemerals_script, 'install_image')
        temp_location = self.make_dir()
        storage_dir = self.prepare_storage_dir()

        install_image_from_simplestreams(
            storage_dir, release=factory.make_name('release'),
            label=factory.make_name('label'), arch=factory.make_name('arch'),
            temp_location=temp_location)

        self.assertItemsEqual([], listdir(temp_location))

    def test_cleans_up_after_failure(self):
        class DeliberateFailure(RuntimeError):
            pass

        self.patch(ephemerals_script, 'install_image').side_effect = (
            DeliberateFailure())
        temp_location = self.make_dir()
        storage_dir = self.prepare_storage_dir()

        self.assertRaises(
            DeliberateFailure,
            install_image_from_simplestreams,
            storage_dir, release=factory.make_name('release'),
            label=factory.make_name('label'), arch=factory.make_name('arch'),
            temp_location=temp_location)

        self.assertItemsEqual([], listdir(temp_location))
