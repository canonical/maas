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
from os.path import (
    abspath,
    exists,
    join,
    )
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
from provisioningserver.utils import ensure_dir
from simplestreams import (
    mirrors,
    objectstores,
    util,
    )


RELEASES = distro_info.UbuntuDistroInfo().supported()
# This must end in a slash, for later concatenation.
RELEASES_URL = 'http://maas.ubuntu.com/images/ephemeral/releases/'
ARCHES = ["amd64/generic", "i386/generic", "armhf/highbank"]

DATA_DIR = "/var/lib/maas/ephemeral"


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
    def __init__(self, local_path, config=None):
        self.local_path = abspath(local_path)
        objectstore = objectstores.FileStore(self._simplestreams_path())
        super(MAASMirrorWriter, self).__init__(config, objectstore)

    def _simplestreams_path(self):
        return join(self.local_path, ".simplestreams")

    def insert_item(self, data, src, target, pedigree, contentsource):
        super(MAASMirrorWriter, self).insert_item(data, src, target, pedigree,
                                                  contentsource)
        path = data.get('path', None)
        flat = util.products_exdata(src, pedigree)
        # TODO: use filters to do this part
        if path and flat.get('ftype') == 'tar.gz':
            self.extract_item(path, flat)

    def _target_dir(self, metadata):
        """ Generate the target directory in maas land. """
        return join(self.local_path, metadata['release'], "ephemeral",
                    metadata['arch'], metadata['version_name'])

    def remove_item(self, data, src, target, pedigree):
        super(MAASMirrorWriter, self).remove_item(data, src, target, pedigree)
        metadata = util.products_exdata(src, pedigree)

        name = get_target_name(**metadata)
        tgt_admin_delete(name)
        remove(get_conf_path(self.local_path, name))

        shutil.rmtree(self._target_dir(metadata))

    def extract_item(self, source, metadata):
        error_cleanups = []
        try:
            tmp = tempfile.mkdtemp(dir=self._simplestreams_path())
            tar = join(self._simplestreams_path(), source)
            subprocess.check_call(["tar", "-Sxzf", tar, "-C", tmp])

            target_dir = self._target_dir(metadata)
            ensure_dir(target_dir)

            def copy_thing(pattern, target):
                things = glob(join(tmp, pattern))
                if len(things) != 1:
                    raise AssertionError(
                        "expected one %s, got %d" % (pattern, len(things)))
                to = join(target_dir, target)
                shutil.copy(things[0], to)
                return to

            copy_thing('*-vmlinuz*', 'linux')
            copy_thing('*-initrd*', 'initrd.gz')
            image = copy_thing('*img', 'disk.img')

            root_tar = join(target_dir, 'dist-root.tar.gz')
            subprocess.check_call(["uec2roottar", image, root_tar])

            name = get_target_name(**metadata)

            write_info_file(
                target_dir, name, release=metadata['release'],
                label=metadata['label'], serial=metadata['version_name'],
                arch=metadata['arch'])
            error_cleanups.append(lambda: clean_up_info_file(target_dir))

            # maas-provision will delete this directory when it finishes.
            provision_tmp = tempfile.mkdtemp(dir=self._simplestreams_path())
            symlink(join(target_dir, 'linux'), join(provision_tmp, 'linux'))
            symlink(join(target_dir, 'initrd.gz'),
                    join(provision_tmp, 'initrd.gz'))
            symlink(root_tar, join(provision_tmp, 'root.tar.gz'))

            # TODO: call src/provisioningserver/pxe/install_image.py directly
            provision_cmd = [
                'maas-provision', 'install-pxe-image',
                '--release=%s' % metadata['release'],
                '--arch=%s' % metadata['arch'],
                # TODO: Something more reasonable for ARM.
                # Simplestreams doesn't really know about this
                # right now, although it might some day for HWE
                # kernels.
                '--subarch=generic',
                '--purpose=commissioning',
                '--image="%s"' % provision_tmp,
                '--symlink=xinstall',
            ]
            subprocess.check_call(provision_cmd)

            tgt_conf_path = join(target_dir, 'tgt.conf')
            write_conf(tgt_conf_path, name, image)
            error_cleanups.append(lambda: remove(tgt_conf_path))

            conf_name = get_conf_path(self.local_path, name)
            if not exists(conf_name):
                symlink(tgt_conf_path, conf_name)

            tgt_admin_update(target_dir, name)
            error_cleanups.append(lambda: tgt_admin_delete(name))
        except Exception:
            for cleanup in reversed(error_cleanups):
                cleanup()
            raise
        finally:
            shutil.rmtree(tmp)


def make_arg_parser(doc):
    """Create an `argparse.ArgumentParser` for this script.

    :param doc: Description of the script, for help output.
    """
    parser = ArgumentParser(description=doc)
    parser.add_argument('--path', action="store",
                        default="streams/v1/index.sjson",
                        help="the path to the index json on the remote mirror")
    parser.add_argument('--url', action='store', default=RELEASES_URL,
                        help="the mirror URL (either remote or file://)")
    parser.add_argument('--output', action='store', default=DATA_DIR,
                        help="The directory to dump maas output in")
    parser.add_argument('--max', action='store', default=1,
                        help="store at most MAX items in the target")
    return parser


def main(args):
    """Import ephemeral images.

    :param args: Command-line arguments, in parsed form.
    """
    source = mirrors.UrlMirrorReader(args.url)
    config = {'max_items': args.max}
    target = MAASMirrorWriter(args.output, config=config)

    set_up_data_dir(args.output)
    target.sync(source, args.path)
