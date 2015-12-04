# Copyright 2014-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Code for the `uec2roottar` script."""

__all__ = [
    'main',
    'make_argparser',
    ]

import argparse
from contextlib import contextmanager
from glob import glob
import os.path
from subprocess import (
    check_call,
    check_output,
)

from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.env import environment_variables
from provisioningserver.utils.fs import tempdir


maaslog = get_maas_logger("uec2roottar")


def make_argparser(description):
    """Create an `ArgumentParser` for this script."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        'image', metavar='IMAGE-FILE', help="Input file: UEC root image.")
    parser.add_argument(
        'output', metavar='TARBALL', help="Output file: root tarball.")
    parser.add_argument(
        '--user', '-u', help="Set output file ownership to USER.")
    return parser


def is_filesystem_file(path):
    """Does the file at `path` look like a filesystem-in-a-file?"""
    # Identify filesystems using the "file" utility.  We'll be parsing the
    # output, so suppress any translation.
    with environment_variables({'LANG': 'C'}):
        output = check_output(['file', path])
    return b"filesystem data" in output


class ImageFileError(Exception):
    """Problem with the given image file."""


def extract_image_from_tarball(tarball, working_dir):
    """Extract image file from `tarball` into `working_dir`, return its path.

    This may extract multiple files into `working_dir`; it looks for files with
    names like `*.img`.  The function only succeeds, however, if there is
    exactly one of those, in the tarball's root directory.
    """
    glob_pattern = '*.img'
    maaslog.debug(
        "Extracting %s from %s into %s.", glob_pattern, tarball, working_dir)
    check_call([
        'tar',
        '-C', working_dir,
        '--wildcards', glob_pattern,
        '-Sxvzf', tarball,
        ])
    # Look for .img files.  Sort just so that if there is more than one image
    # file, we'll produce a consistent error message.
    candidates = sorted(glob(os.path.join(working_dir, glob_pattern)))
    if len(candidates) == 0:
        raise ImageFileError(
            "Tarball %s does not contain any %s." % (tarball, glob_pattern))
    if len(candidates) > 1:
        raise ImageFileError(
            "Tarball %s contains multiple image files: %s."
            % (tarball, ', '.join(candidates)))
    [image] = candidates
    return image


def get_image_file(path, temp_dir):
    """Return image file at, or contained in tarball at, `path`.

    :param path: Path to the image file.  Must point to either a file
        containing a filesystem, or a tarball containing one, of the same
        base name.
    :param temp_dir: A temporary working directory.  If the image needs to be
        extracted from a tarball, the tarball will be extracted here.
    """
    if is_filesystem_file(path):
        # Easy.  This is the actual image file.
        return path
    elif path.endswith('.tar.gz'):
        # Tarball.  Extract image file.
        return extract_image_from_tarball(path, temp_dir)
    else:
        raise ImageFileError(
            "Expected '%s' to be either a filesystem file, or "
            "a gzipped tarball containing one." % path)


def unmount(mountpoint):
    """Unmount filesystem at given mount point.

    If this fails, it logs the error as well as raising it.  This means that
    error code paths can suppress the exception without depriving the user of
    the information.
    """
    try:
        check_call(['umount', mountpoint])
    except BaseException as e:
        maaslog.error("Could not unmount %s: %s", mountpoint, e)
        raise


@contextmanager
def loop_mount(image, mountpoint):
    """Context manager: temporarily loop-mount `image` at `mountpoint`."""
    check_call(['mount', '-o', 'ro', image, mountpoint])
    try:
        yield
    except:
        try:
            unmount(mountpoint)
        except Exception:
            # This is probably a secondary error resulting from the original
            # problem.  Stick with the original exception.
            pass
        raise
    else:
        # Unmount after successful run.  If this fails, let the exception
        # propagate.
        unmount(mountpoint)


def tar_supports_xattr_opts():
    """Returns True if the system's tar supports the 'xattrs' options."""
    out = check_output(['tar', '--help'])
    return b"xattr" in out


def extract_image(image, output):
    """Loop-mount `image`, and tar its contents into `output`."""

    xattr_opts = []
    if tar_supports_xattr_opts():
        # Only add the xattrs options if tar supports it.
        # For insance tar on 12.04 does *not* support xattrs.
        xattr_opts = ['--xattrs', '--xattrs-include=*']
    with tempdir() as mountpoint:
        cmd = ['tar'] + xattr_opts + [
            # Work from mountpoint as the current directory.
            '-C', mountpoint,
            # Options:
            #    -c: Create tarfile.
            #    -p: Preserve permissions.
            #    -S: Handle sparse files efficiently (images have those).
            #    -z: Compress using gzip.
            #    -f: Work on given tar file.
            '-cpSzf', output,
            '--numeric-owner',
            # Tar up the "current directory": the mountpoint.
            '.',
            ]

        with loop_mount(image, mountpoint):
            check_call(cmd)


def set_ownership(path, user=None):
    """Set file ownership to `user` if specified."""
    if user is not None:
        maaslog.debug("Setting file owner to %s.", user)
        check_call(['/bin/chown', user, path])


def main(args):
    """Do the work: loop-mount image, write contents to output file."""
    output = args.output
    maaslog.debug("Converting %s to %s.", args.image, output)
    with tempdir() as working_dir:
        image = get_image_file(args.image, working_dir)
        extract_image(image, output)
    set_ownership(output, args.user)
    maaslog.debug("Finished.  Wrote to %s.", output)
