# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Tests for the `uec2roottar` script and its supporting module.."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = []

import os
import os.path
from subprocess import CalledProcessError

from maastesting.factory import factory
from maastesting.matchers import (
    MockAnyCall,
    MockCalledOnceWith,
    MockNotCalled,
    )
from maastesting.testcase import MAASTestCase
import mock
from provisioningserver.import_images import uec2roottar
from testtools.matchers import HasLength
from testtools.testcase import ExpectedException


def make_image_name(suffix='.img'):
    """Create an image file name (but not the actual file)."""
    return factory.make_name('root') + suffix


def make_image(testcase, contents=None, suffix='.img'):
    """Create an image file."""
    name = make_image_name(suffix)
    return testcase.make_file(name=name, contents=contents)


def make_tarball_name(prefix='tarball'):
    """Create an arbitrary name for a tarball."""
    return factory.make_name(prefix) + '.tar.gz'


def make_roottar_location(testcase):
    """Create a name for an output root tarball, in an empty directory."""
    name = make_tarball_name('root')
    return os.path.join(testcase.make_dir(), name)


def patch_is_filesystem_file(testcase, answer):
    """Patch `is_filesystem_file` to return the given answer."""
    testcase.patch(uec2roottar, 'is_filesystem_file').return_value = answer


class TestMakeArgParser(MAASTestCase):
    """Tests for `make_argparser`."""

    def test__defines_expected_options(self):
        image = make_image(self)
        output = make_roottar_location(self)
        user = factory.make_name('user')

        parser = uec2roottar.make_argparser(factory.make_string())
        args = parser.parse_args([image, output, '--user', user])

        self.assertEqual(
            (
                image,
                output,
                user,
            ),
            (
                args.image,
                args.output,
                args.user,
            ))

    def test__user_defaults_to_None(self):
        parser = uec2roottar.make_argparser(factory.make_string())
        args = parser.parse_args(
            [make_image(self), make_roottar_location(self)])
        self.assertIsNone(args.user)


class TestIsFilesystemFile(MAASTestCase):
    """Tests for `is_filesystem_file`."""

    def test__returns_True_if_file_looks_like_filesystem(self):
        image = make_image(self, suffix='.img')
        self.patch(uec2roottar, 'check_output').return_value = (
            ("%s: filesystem data" % image).encode('utf-8'))
        self.assertTrue(uec2roottar.is_filesystem_file(image))

    def test__returns_False_for_tarball(self):
        image = make_image(self, suffix='.tar.gz')
        self.patch(uec2roottar, 'check_output').return_value = (
            ("%s: gzip compressed data, was ..." % image).encode('utf-8'))
        self.assertFalse(uec2roottar.is_filesystem_file(image))

    def test__calls_file_with_C_language_setting(self):
        env_during_invocation = {}

        def fake_check_output(*args, **kwargs):
            env_during_invocation.update(os.environ)
            return b''

        self.patch(uec2roottar, 'check_output', fake_check_output)

        uec2roottar.is_filesystem_file(make_image(self))

        self.assertEqual('C', env_during_invocation.get('LANG'))


class TestExtractImageFromTarball(MAASTestCase):
    """Tests for `extract_image_from_tarball`."""

    def test__extracts_image(self):
        tarball = make_tarball_name()
        self.patch(uec2roottar, 'check_call')
        # Cheat: patch away extraction of the tarball, but pass a temporary
        # directory with an image already in it.  The function will think it
        # just extracted the image from the tarball.
        image = make_image(self)
        working_dir = os.path.dirname(image)

        result = uec2roottar.extract_image_from_tarball(tarball, working_dir)

        self.assertThat(
            uec2roottar.check_call,
            MockCalledOnceWith([
                'tar',
                '-C', working_dir,
                '--wildcards', '*.img',
                '-Sxvzf',
                tarball,
                ]))
        self.assertEqual(image, result)

    def test__ignores_other_files(self):
        tarball = make_tarball_name()
        self.patch(uec2roottar, 'check_call')
        # Make the function think that it found two files in the tarball: an
        # image and some other file.
        image = make_image(self)
        working_dir = os.path.dirname(image)
        # This other file doesn't upset things, because it doesn't look like
        # an image file.
        factory.make_file(working_dir)

        self.assertEqual(
            image,
            uec2roottar.extract_image_from_tarball(tarball, working_dir))

    def test__fails_if_no_image_found(self):
        tarball = make_tarball_name()
        self.patch(uec2roottar, 'check_call')
        empty_dir = self.make_dir()
        error = self.assertRaises(
            uec2roottar.ImageFileError,
            uec2roottar.extract_image_from_tarball, tarball, empty_dir)
        self.assertEqual(
            "Tarball %s does not contain any *.img." % tarball,
            unicode(error))

    def test__fails_if_multiple_images_found(self):
        tarball = make_tarball_name()
        self.patch(uec2roottar, 'check_call')
        working_dir = self.make_dir()
        files = sorted(
            factory.make_file(working_dir, name=make_image_name())
            for _ in range(2))
        error = self.assertRaises(
            uec2roottar.ImageFileError,
            uec2roottar.extract_image_from_tarball, tarball, working_dir)
        self.assertEqual(
            "Tarball %s contains multiple image files: %s."
            % (tarball, ', '.join(files)),
            unicode(error))


class TestGetImageFile(MAASTestCase):
    """Tests for `get_image_file`."""

    def test__returns_actual_image_file_unchanged(self):
        patch_is_filesystem_file(self, True)
        image = make_image(self)
        self.assertEqual(
            image,
            uec2roottar.get_image_file(image, factory.make_name('dir')))

    def test__extracts_tarball_into_temp_dir(self):
        patch_is_filesystem_file(self, False)
        tarball = make_tarball_name()
        temp_dir = self.make_dir()
        image = make_image_name()
        patch = self.patch(uec2roottar, 'extract_image_from_tarball')
        patch.return_value = image
        result = uec2roottar.get_image_file(tarball, temp_dir)
        self.assertEqual(image, result)
        self.assertThat(patch, MockCalledOnceWith(tarball, temp_dir))

    def test__rejects_other_files(self):
        patch_is_filesystem_file(self, False)
        filename = factory.make_name('weird-file')
        error = self.assertRaises(
            uec2roottar.ImageFileError,
            uec2roottar.get_image_file, filename, factory.make_name('dir'))
        self.assertEqual(
            "Expected '%s' to be either a filesystem file, or a "
            "gzipped tarball containing one." % filename,
            unicode(error))


class TestUnmount(MAASTestCase):
    """Tests for `unmount`."""

    def test__calls_umount(self):
        self.patch(uec2roottar, 'check_call')
        mountpoint = factory.make_name('mount')
        uec2roottar.unmount(mountpoint)
        self.assertThat(
            uec2roottar.check_call,
            MockCalledOnceWith(['umount', mountpoint]))

    def test__propagates_failure(self):
        failure = CalledProcessError(9, factory.make_name('delibfail'))
        self.patch(uec2roottar, 'check_call').side_effect = failure
        self.patch(uec2roottar, 'maaslog')
        mountpoint = factory.make_name('mount')
        self.assertRaises(CalledProcessError, uec2roottar.unmount, mountpoint)
        self.assertThat(
            uec2roottar.maaslog.error,
            MockCalledOnceWith(
                "Could not unmount %s: %s", mountpoint, failure))


class TestLoopMount(MAASTestCase):
    """Tests for `loop_mount`."""

    def test__mounts_and_unmounts_image(self):
        image = make_image_name()
        self.patch(uec2roottar, 'check_call')
        mountpoint = factory.make_name('mount')

        calls_before = len(uec2roottar.check_call.mock_calls)
        with uec2roottar.loop_mount(image, mountpoint):
            calls_during = len(uec2roottar.check_call.mock_calls)
        calls_after = len(uec2roottar.check_call.mock_calls)

        self.assertEqual(
            (0, 1, 2),
            (calls_before, calls_during, calls_after))
        self.assertThat(
            uec2roottar.check_call,
            MockAnyCall(['mount', '-o', 'ro', image, mountpoint]))
        self.assertThat(
            uec2roottar.check_call,
            MockAnyCall(['umount', mountpoint]))

    def test__cleans_up_after_failure(self):
        class DeliberateException(Exception):
            pass

        self.patch(uec2roottar, 'check_call')
        image = make_image_name()
        mountpoint = factory.make_name('mount')
        with ExpectedException(DeliberateException):
            with uec2roottar.loop_mount(image, mountpoint):
                raise DeliberateException()

        self.assertThat(
            uec2roottar.check_call, MockAnyCall(['umount', mountpoint]))


class TestExtractImage(MAASTestCase):
    """Tests for `extract_image`."""

    def extract_command_line(self, call):
        """Extract the command line from a `mock.call` for `check_call`."""
        _, args, _ = call
        [command] = args
        return command

    def test__extracts_image(self):
        image = make_image_name()
        output = make_tarball_name()
        self.patch(uec2roottar, 'check_call')
        uec2roottar.extract_image(image, output)
        self.assertThat(uec2roottar.check_call.mock_calls, HasLength(3))
        [mount_call, tar_call, umount_call] = uec2roottar.check_call.mock_calls
        self.assertEqual('mount', self.extract_command_line(mount_call)[0])
        tar_command = self.extract_command_line(tar_call)
        self.assertEqual(['tar', '-C'], tar_command[:2])
        self.assertEqual('umount', self.extract_command_line(umount_call)[0])


class TestSetOwnership(MAASTestCase):
    """Tests for `set_ownership`."""

    def test__does_nothing_if_no_user_specified(self):
        self.patch(uec2roottar, 'check_call')
        uec2roottar.set_ownership(make_tarball_name(), user=None)
        self.assertThat(uec2roottar.check_call, MockNotCalled())

    def test__calls_chown_if_user_specified(self):
        self.patch(uec2roottar, 'check_call')
        user = factory.make_name('user')
        tarball = make_tarball_name()
        uec2roottar.set_ownership(tarball, user=user)
        self.assertThat(
            uec2roottar.check_call,
            MockCalledOnceWith(['/bin/chown', user, tarball]))


class TestUEC2RootTar(MAASTestCase):
    """Integration tests for `uec2roottar`."""

    def make_args(self, **kwargs):
        """Fake an `argparser` arguments object."""
        args = mock.Mock()
        for key, value in kwargs.items():
            setattr(args, key, value)
        return args

    def test__integrates(self):
        image_name = factory.make_name('root-image') + '.img'
        image = self.make_file(name=image_name)
        output_name = factory.make_name('root-tar') + '.tar.gz'
        output = os.path.join(self.make_dir(), output_name)
        args = self.make_args(image=image, output=output)
        self.patch(uec2roottar, 'check_call')
        patch_is_filesystem_file(self, True)

        uec2roottar.main(args)

        self.assertThat(
            uec2roottar.is_filesystem_file, MockCalledOnceWith(image))
