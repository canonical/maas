#!/usr/bin/env python2.7
# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""" Download and import ephemeral images for maas. """

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type


import argparse
import codecs
from errno import EEXIST
from glob import glob
from os import (
    makedirs,
    remove,
    symlink,
    )
from os.path import (
    abspath,
    exists,
    join,
    )
import re
import shutil
import subprocess
import tempfile
from textwrap import dedent

import distro_info
from simplestreams import (
    mirrors,
    objectstores,
    util,
    )


RELEASES = distro_info.UbuntuDistroInfo().supported()
RELEASES_URL = 'http://maas.ubuntu.com/images/'
ARCHES = ["amd64/generic", "i386/generic", "armhf/highbank"]

DATA_DIR = "/var/lib/maas/simplestreams"

TGT_CONF_CONTENT = "include {path}\ndefault-driver iscsi\n"

TGT_CONF_TEMPL = dedent("""\
    <target iqn.2004-05.com.ubuntu:maas:{target_name}>
        readonly 1
        backing-store "{image}"
    </target>
    """)

TGT_ADMIN = ["tgt-admin", "--conf", "/etc/tgt/targets.conf"]

NAME_FORMAT = 'maas-{release}-{version}-{arch}-{version_name}'


def mkdir_p(d):
    try:
        makedirs(d)
    except OSError as e:
        if e.errno != EEXIST:
            raise


def tgt_conf_d(path):
    return join(path, 'tgt.conf.d')


def tgt_admin_delete(name):
    subprocess.check_call(TGT_ADMIN + ["--delete", name])


def tgt_admin_update(target_dir, name):
    def cleanup_on_fail():
        tgt_admin_delete(name)
        remove(join(target_dir, 'tgt.conf'))
        shutil.move(join(target_dir, 'info'), join(target_dir, 'info.failed'))
    try:
        subprocess.check_call(TGT_ADMIN + ["--update", name])
        status = subprocess.check_output(TGT_ADMIN + ["--show"])
        m = re.match('^Target [0-9][0-9]*: %s' % name, status)
        if not m:
            cleanup_on_fail()
            raise Exception("failed tgt-admin add for " + name)
    except subprocess.CalledProcessError:
        cleanup_on_fail()
        raise


class MAASMirrorWriter(mirrors.ObjectStoreMirrorWriter):
    def __init__(self, local_path, config=None):
        self.local_path = local_path
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

        name = NAME_FORMAT.format(metadata)
        tgt_admin_delete(name)
        remove(join(tgt_conf_d(self.local_path), name + ".conf"))

        shutil.rmtree(self._target_dir(metadata))

    def extract_item(self, source, metadata):
        try:
            tmp = tempfile.mkdtemp(dir=self._simplestreams_path())
            tar = join(self._simplestreams_path(), source)
            subprocess.check_call(["tar", "-Sxzf", tar, "-C", tmp])

            target_dir = self._target_dir(metadata)
            mkdir_p(target_dir)

            def copy_thing(pattern, target):
                things = glob(join(tmp, pattern))
                if len(things) != 1:
                    raise AssertionError(
                        "expected one %s, got %d" % (pattern, len(things)))
                shutil.copy(things[0], join(target_dir, target))

            copy_thing('*-vmlinuz*', 'linux')
            copy_thing('*-initrd*', 'initrd.gz')
            copy_thing('*disk.img', 'disk.img')
            root_tar = source[:-len('.tar.gz')] + '-root.tar.gz'
            shutil.copy(root_tar, join(target_dir, 'dist-root.tar.gz'))
            with codecs.open(join(target_dir, 'info'), 'w', 'utf-8') as f:
                info = ["release", "stream", "label", "serial", "arch", "url",
                        "name"]
                # maas calls this "serial" instead of "version_name"
                metadata['serial'] = metadata['version_name']
                fmt = '\n'.join("%s={%s}" % (i, i) for i in info)
                f.write(fmt.format(metadata) + '\n')

            # maas-provision deletes this directory
            provision_tmp = tempfile.mkdtemp(dir=self._simplestreams_path())
            shutil.copy(join(target_dir, 'linux'), join(provision_tmp, 'linux'))
            shutil.copy(join(target_dir, 'initrd.gz'),
                        join(provision_tmp, 'initrd.gz'))
            shutil.copy(root_tar, join(provision_tmp, 'root.tar.gz'))
            provision_cmd = ['maas-provision', 'install-pxe-image',
                             '--arch=' + metadata['arch'],
                             '--purpose="commissioning"',
                             '--image="%s"' % provision_tmp,
                             '--symlink="xinstall"']
            subprocess.check_call(provision_cmd)

            name = NAME_FORMAT.format(metadata)

            tgt_conf_path = join(target_dir, 'tgt.conf')
            with codecs.open(tgt_conf_path, 'w', 'utf-8') as f:
                image = join(target_dir, "disk.img")
                f.write(TGT_CONF_TEMPL.format(target_name=name, image=image))

            tgt_admin_update(target_dir, name)

            conf_name = join(tgt_conf_d(self.local_path), '%s.conf' % name)
            symlink(abspath(tgt_conf_path), conf_name)
        finally:
            shutil.rmtree(tmp)


def setup_data_dir(data_dir):
    mkdir_p(data_dir)
    mkdir_p(tgt_conf_d(data_dir))

    tgt_conf = join(data_dir, 'tgt.conf')
    if not exists(tgt_conf):
        with codecs.open(tgt_conf, 'w', 'utf-8') as f:
            f.write(TGT_CONF_CONTENT.format(path=tgt_conf_d(data_dir)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument('--path', action="store",
                        default="streams/v1/index.sjson",
                        help="the path to the index json on the remote mirror")
    parser.add_argument('--url', action='store', default=RELEASES_URL,
                        help="the mirror URL (either remote or file://)")
    parser.add_argument('--output', action='store', default=DATA_DIR,
                        help="The directory to dump maas output in")
    parser.add_argument('--max', action='store', default=1,
                        help="store at most MAX items in the target")

    cmdargs = parser.parse_args()

    source = mirrors.UrlMirrorReader(cmdargs.url)
    config = {'max_items': cmdargs.max}
    target = MAASMirrorWriter(cmdargs.output, config=config)

    setup_data_dir(cmdargs.output)
    target.sync(source, cmdargs.path)


if __name__ == '__main__':
    main()

# vi: ts=4 expandtab
