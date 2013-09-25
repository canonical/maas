#!/usr/bin/env python2.7
# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Script code for `maas-import-ephemerals.py`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'main',
    'make_arg_parser',
    ]

from argparse import ArgumentParser
from glob import glob
from os import (
    remove,
    symlink,
    )
import os.path
import shutil
import subprocess
import tempfile

import distro_info
from provisioningserver.import_images.tgt import (
    clean_up_info_file,
    get_conf_path,
    get_target_name,
    set_up_data_dir,
    tgt_admin_delete,
    tgt_admin_update,
    write_conf,
    write_info_file,
    )
from provisioningserver.pxe.install_image import install_image
from provisioningserver.utils import ensure_dir
from simplestreams import (
    filters,
    mirrors,
    objectstores,
    util,
    )


RELEASES = distro_info.UbuntuDistroInfo().supported()
# This must end in a slash, for later concatenation.
RELEASES_URL = 'http://maas.ubuntu.com/images/ephemeral/releases/'

DEFAULT_FILTERS = ['arch~(amd64|i386|armhf)']

PRODUCTS_REGEX = 'com[.]ubuntu[.]maas:ephemeral:.*'

DATA_DIR = "/var/lib/maas/ephemeral"

DEFAULT_KEYRING = "/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg"


def copy_file_by_glob(source_dir, pattern, target_dir, target):
    """Copy a single file, identified by a glob pattern.

    :param source_dir: Directory where the file should be.
    :param pattern: A glob pattern identifying the single file to be copied.
    :param target_dir: Directory to copy to.
    :param target: Name for the copy.
    :return: Full path to the copy.
    """
    matches = glob(os.path.join(source_dir, pattern))
    if len(matches) != 1:
        raise AssertionError(
            "expected one %s, found %d" % (pattern, len(matches)))
    [original] = matches
    to = os.path.join(target_dir, target)
    shutil.copy(original, to)
    return to


def call_uec2roottar(*args):
    """Invoke `uec2roottar` with the given arguments.

    Here only so tests can stub it out.
    """
    subprocess.check_call(["uec2roottar"] + list(args))


def extract_image_tarball(tarball, target_dir, temp_location=None):
    """Extract image from simplestreams tarball into `target_dir`.

    This copies the kernel, initrd, and .img file from the tarball into the
    target directory.  The exact names of these files in the tarball may vary,
    but they will always be installed as `linux`, `initrd.gz`, and `disk.img`.

    Finally, this will run uec2roottar on the `disk.image` file, in order to
    create a `dist-root.tar.gz` tarball.

    :param tarball: Path to a tar file containing the image.
    :param target_dir: Directory where the image files should be installed.
    :param temp_location: Optional location where the function may create a
        temporary working directory for extracting the tarball.
    """
    tmp = tempfile.mkdtemp(dir=temp_location)
    try:
        # Unpack tarball.  The -S flag is for sparse files; the disk image
        # may have holes.
        subprocess.check_call(["tar", "-Sxzf", tarball, "-C", tmp])

        copy_file_by_glob(tmp, '*-vmlinuz*', target_dir, 'linux')
        copy_file_by_glob(tmp, '*-initrd*', target_dir, 'initrd.gz')
        image = copy_file_by_glob(tmp, '*img', target_dir, 'disk.img')
    finally:
        shutil.rmtree(tmp)

    call_uec2roottar(image, os.path.join(target_dir, 'dist-root.tar.gz'))


def create_symlinked_image_dir(original_dir, temp_location=None):
    """Create a boot image directory, containing symlinks to an original.

    The result will be a temporary directory (so be sure to clean it up!)
    containing `linux`, `initrd.gz`, and `root.tar.gz` as in the original
    directory.

    For unclear historical reasons, `root.tar.gz` must be called
    `dist-root.tar.gz` in the original directory even though its link in
    the resulting directory will be called `root.tar.gz`.

    :param original_dir: A directory containing the actual boot-image files.
    :param temp_location: An optional location where the function may create
        its boot image directory.
    :return: Path to a temporary directory containing a boot image in the
        form of symlinks.
    """
    image_dir = tempfile.mkdtemp(dir=temp_location)
    try:
        symlink(
            os.path.join(original_dir, 'linux'),
            os.path.join(image_dir, 'linux'))
        symlink(
            os.path.join(original_dir, 'initrd.gz'),
            os.path.join(image_dir, 'initrd.gz'))
        symlink(
            os.path.join(original_dir, 'dist-root.tar.gz'),
            os.path.join(image_dir, 'root.tar.gz'))
    except:
        shutil.rmtree(image_dir)
        raise
    return image_dir


def install_image_from_simplestreams(storage_dir, release, arch,
                                     subarch='generic',
                                     purpose='commissioning',
                                     symlink='xinstall', temp_location=None):
    """Install boot image, based on files downloaded from simplestreams.

    :param storage_dir: Directory containing the image files (`linux`,
        `initrd.gz`, `dist-root.tar.gz`).  The image that will be installed is
        a directory of symlinks to these files.
    :param release: Release name to install, e.g. "precise".
    :param arch: Architecture for the image, e.g. "i386".
    :param subarch: Sub-architecture.  Defaults to "generic".
    :param purpose: Boot purpose for the image.  Defaults to `commissioning`.
    :param symlink: Alternate name for boot image.  If given, in addition to
        the image directory itself, this will also install a symlink to the
        installed image directory under this alternate name.
    :param temp_location: Optional location where temporary image directories
        and such may be created.
    """
    # install_image will delete this directory when it finishes.
    provision_tmp = create_symlinked_image_dir(
        storage_dir, temp_location=temp_location)

    try:
        install_image(
            provision_tmp, release=release, arch=arch, subarch=subarch,
            purpose=purpose, symlink=symlink)
    finally:
        shutil.rmtree(provision_tmp, ignore_errors=True)


# The basic process for importing ephemerals is as follows:
#   1. do the simplestreams mirror (this is mostly handled by simplestreams);
#      the output is one .tar.gz for each arch, which itself contains a
#        *.img - the root filesystem image
#        *vmlinuz* - kernel
#        *initrd* - initramfs
#   2. for each release/arch/serial combo, we extract the simplstreams tar and
#      copy the kernel/disk/image to the appropriate location in DATA_DIR.
#   2.1. create a root.tar.gz, which is basically just a copy of disk.img in
#        .tar.gz format (fastpath only understands .tar.gz, .tar.gz compresses
#        better, etc.)
#   3. Run maas-provision. Since maas-provision deletes its data when it's
#      done, we have to create _another_ directory and symlink (to avoid
#      copying) everything over. This is annoying.
#   4. generate tgt.conf, run tgt-admin, and symlink things to the right
#      places.


class MAASMirrorWriter(mirrors.ObjectStoreMirrorWriter):
    """Implement a local simplestreams mirror."""

    def __init__(self, local_path, config=None, delete=False,
                 item_filters=None, product_regex=PRODUCTS_REGEX):
        self.local_path = os.path.abspath(local_path)
        self.delete = delete

        # Any user specified filters such as arch~(amd64|i386) are in
        # addition to our selecting only tar.gz files.  That's the only type
        # of file we know how to unpack.
        self.item_filters = item_filters or []
        self.item_filters.append('ftype=tar.gz')
        self.item_filters = filters.get_filters(self.item_filters)

        self.product_filters = [
            filters.ItemFilter('product_name~' + product_regex)]

        objectstore = objectstores.FileStore(self._simplestreams_path())
        super(MAASMirrorWriter, self).__init__(config, objectstore)

    def _simplestreams_path(self):
        """Return the local directory where we mirror simplestreams data."""
        return os.path.join(self.local_path, ".simplestreams")

    def filter_product(self, data, src, target, pedigree):
        """See `ObjectStoreMirrorWriter`."""
        return filters.filter_item(self.product_filters, data, src, pedigree)

    def filter_item(self, data, src, target, pedigree):
        """See `ObjectStoreMirrorWriter`."""
        return filters.filter_item(self.item_filters, data, src, pedigree)

    def insert_item(self, data, src, target, pedigree, contentsource):
        """See `ObjectStoreMirrorWriter`."""
        super(MAASMirrorWriter, self).insert_item(
            data, src, target, pedigree, contentsource)
        path = data.get('path', None)
        flat = util.products_exdata(src, pedigree)
        if path is not None:
            self.extract_item(path, flat)

    def _target_dir(self, metadata):
        """ Generate the target directory in maas land. """
        return os.path.join(
            self.local_path, metadata['release'], "ephemeral",
            metadata['arch'], metadata['version_name'])

    def remove_item(self, data, src, target, pedigree):
        """See `ObjectStoreMirrorWriter`.

        Remove items from our local mirror that are no longer available
        upstream.
        """
        if not self.delete:
            # Caller didn't ask for obsolete items to be deleted.
            return

        super(MAASMirrorWriter, self).remove_item(data, src, target, pedigree)
        metadata = util.products_exdata(src, pedigree)

        name = get_target_name(**metadata)
        tgt_admin_delete(name)
        remove(get_conf_path(self.local_path, name))

        shutil.rmtree(self._target_dir(metadata))

    def extract_item(self, source, metadata):
        """See `ObjectStoreMirrorWriter`."""
        arch = metadata['arch']
        release = metadata['release']
        version = metadata['version']
        version_name = metadata['version_name']
        label = metadata['label']
        target_dir = self._target_dir(metadata)
        name = get_target_name(
            release=release, version=version, arch=arch,
            version_name=version_name)
        tarball = os.path.join(self._simplestreams_path(), source)

        error_cleanups = []
        try:
            ensure_dir(target_dir)
            extract_image_tarball(
                tarball, target_dir, temp_location=self._simplestreams_path())

            write_info_file(
                target_dir, name, release=release, label=label,
                serial=version_name, arch=arch)
            error_cleanups.append(lambda: clean_up_info_file(target_dir))

            # HACK: In order to be backwards compatible, we need to deploy
            # ARM kernels with subarch=highbank. However, the special
            # hardware support required there is now available in stock
            # kernels, so we can use the same one everywhere.
            # TODO: Something more reasonable for ARM.
            # Simplestreams doesn't really know about this
            # right now, although it might some day for HWE
            # kernels.
            install_image_from_simplestreams(
                target_dir, release=release, arch=arch,
                temp_location=self._simplestreams_path())
            if arch == 'armhf':
                install_image_from_simplestreams(
                    target_dir, release=release, arch=arch, subarch='highbank',
                    temp_location=self._simplestreams_path())

            tgt_conf_path = os.path.join(target_dir, 'tgt.conf')
            write_conf(
                tgt_conf_path, name, os.path.join(target_dir, 'disk.img'))
            error_cleanups.append(lambda: remove(tgt_conf_path))

            conf_name = get_conf_path(self.local_path, name)
            if not os.path.exists(conf_name):
                symlink(tgt_conf_path, conf_name)

            tgt_admin_update(target_dir, name)
            error_cleanups.append(lambda: tgt_admin_delete(name))
        except Exception:
            for cleanup in reversed(error_cleanups):
                cleanup()
            raise


def make_arg_parser(doc):
    """Create an `argparse.ArgumentParser` for this script.

    :param doc: Description of the script, for help output.
    """
    parser = ArgumentParser(description=doc)
    parser.add_argument(
        '--path', action="store", default="streams/v1/index.sjson",
        help="the path to the index json on the remote mirror")
    parser.add_argument(
        '--url', action='store', default=RELEASES_URL,
        help="the mirror URL (either remote or file://)")
    parser.add_argument(
        '--output', action='store', default=DATA_DIR,
        help="The directory to dump maas output in")
    parser.add_argument(
        '--max', action='store', default=1,
        help="store at most MAX items in the target")
    parser.add_argument(
        '--keyring', action='store', default=DEFAULT_KEYRING,
        help='gpg keyring for verifying boot image metadata')
    parser.add_argument(
        '--delete', action='store_true', default=False,
        help="Delete local copies of images when no longer available?")
    parser.add_argument(
        '--products', action='store', default=PRODUCTS_REGEX,
        help="regex matching products to import, e.g. "
             "com.ubuntu.maas.daily:ephemerals:.* for daily")
    parser.add_argument(
        'filters', nargs='*', default=DEFAULT_FILTERS,
        help="filters over image metadata, e.g. arch=i386 release=precise")
    return parser


def main(args):
    """Import ephemeral images.

    :param args: Command-line arguments, in parsed form.
    """
    def verify_signature(content, path):
        return util.read_signed(content, keyring=args.keyring)

    source = mirrors.UrlMirrorReader(args.url, policy=verify_signature)
    config = {'max_items': args.max}
    target = MAASMirrorWriter(args.output, config=config, delete=args.delete)

    set_up_data_dir(args.output)
    target.sync(source, args.path)
