# Copyright 2013 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'main',
    'available_boot_resources',
    ]

from collections import defaultdict
from datetime import datetime
import errno
import glob
from gzip import GzipFile
from json import dumps as jsondumps
import os
from textwrap import dedent

from provisioningserver.config import Config
from provisioningserver.pxe.install_bootloader import install_bootloader
from provisioningserver.utils import call_and_check
from simplestreams.contentsource import FdContentSource
from simplestreams.mirrors import (
    BasicMirrorWriter,
    UrlMirrorReader,
    )
from simplestreams.objectstores import FileStore
from simplestreams.util import (
    item_checksums,
    products_exdata,
    )


def create_empty_hierarchy():
    return defaultdict(create_empty_hierarchy)


def boot_walk(boot, func):
    for arch in boot:
        for subarch in boot[arch]:
            for release in boot[arch][subarch]:
                func(arch, subarch, release, boot[arch][subarch][release])


def boot_merge(boot1, boot2, filters=None):

    def filter_func(arch, subarch, release):
        for filter in filters:
            item_matches = (
                filter['release'] in ('*', release) and
                filter['arch'] in ('*', arch) and
                (
                    '*' in filter['subarches'] or
                    subarch in filter['subarches']
                )
            )
            if item_matches:
                return True
        return False

    def merge_func(arch, subarch, release, boot_resource):
        if filters and not filter_func(arch, subarch, release):
            return
        boot1[arch][subarch][release] = boot_resource

    boot_walk(boot2, merge_func)


def boot_reverse(boot):
    reverse = create_empty_hierarchy()

    def reverse_func(arch, subarch, release, boot_resource):
        content_id = boot_resource['content_id']
        product_name = boot_resource['product_name']
        existent = list(reverse[content_id][product_name])
        reverse[content_id][product_name] = [subarch] + existent

    boot_walk(boot, reverse_func)
    return reverse


def tgt_entry(arch, subarch, release, image):
    prefix = 'iqn.2004-05.com.ubuntu:maas'
    target_name = 'ephemeral-%s-%s-%s' % (arch, subarch, release)
    entry = dedent("""\
    <target {prefix}:{target_name}>
        readonly 1
        allow-in-use yes
        backing-store "{image}"
        driver iscsi
    </target>
    """).format(prefix=prefix, target_name=target_name, image=image)
    return entry


class RepoDumper(BasicMirrorWriter):

    def __init__(self):
        super(RepoDumper, self).__init__({'max_items': 1})

    def dump(self, path):
        self._boot = create_empty_hierarchy()
        reader = UrlMirrorReader(path)
        super(RepoDumper, self).sync(reader, 'streams/v1/index.sjson')
        return self._boot

    def load_products(self, path=None, content_id=None):
        return

    def item_cleanup(self, item):
        keys_to_keep = ['content_id', 'product_name', 'version_name', 'path']
        compact_item = {key: item[key] for key in keys_to_keep}
        return compact_item

    def insert_item(self, data, src, target, pedigree, contentsource):
        item = products_exdata(src, pedigree)
        arch, subarches = item['arch'], item['subarches']
        release = item['release']
        compact_item = self.item_cleanup(item)
        for subarch in subarches.split(','):
            self._boot[arch][subarch][release] = compact_item


class RepoWriter(BasicMirrorWriter):

    def __init__(self, root_path, cache_path, info):
        self._root_path = os.path.abspath(root_path)
        self._info = info
        self._cache = FileStore(os.path.abspath(cache_path))
        super(RepoWriter, self).__init__({'max_items': 1})

    def write(self, path):
        reader = UrlMirrorReader(path)
        super(RepoWriter, self).sync(reader, 'streams/v1/index.sjson')

    def load_products(self, path=None, content_id=None):
        return

    def filter_product(self, data, src, target, pedigree):
        item = products_exdata(src, pedigree)
        content_id, product_name = item['content_id'], item['product_name']
        return (
            content_id in self._info and
            product_name in self._info[content_id]
        )

    def insert_uncompressed(self, tag, checksums, size, contentsource):
        self._cache.insert(
            tag, contentsource, checksums, mutable=False, size=size)
        return self._cache._fullpath(tag)

    def insert_compressed(self, tag, checksums, size, contentsource):
        # TODO: Bake root.tar.gz required by fast-path installer (uec2roottar)
        uncompressed_tag = 'uncompressed-%s' % tag
        compressed_path = self._cache._fullpath(tag)
        uncompressed_path = self._cache._fullpath(uncompressed_tag)
        if not os.path.isfile(uncompressed_path):
            self._cache.insert(tag, contentsource, checksums,
                               mutable=False, size=size)
            compressed_source = FdContentSource(GzipFile(compressed_path))
            self._cache.insert(uncompressed_tag, compressed_source,
                               mutable=False)
            self._cache.remove(tag)
        return uncompressed_path

    def insert_item(self, data, src, target, pedigree, contentsource):
        item = products_exdata(src, pedigree)
        checksums = item_checksums(data)
        tag = checksums['md5']
        size = data['size']
        if data['path'].endswith('.gz'):
            src = self.insert_compressed(tag, checksums, size, contentsource)
        else:
            src = self.insert_uncompressed(tag, checksums, size, contentsource)
        for subarch in self._info[item['content_id']][item['product_name']]:
            dst_folder = os.path.join(
                self._root_path, item['arch'], subarch, item['release'])
            if not os.path.exists(dst_folder):
                os.makedirs(dst_folder)
            os.link(src, os.path.join(dst_folder, item['ftype']))


def available_boot_resources(root):
    for resource_path in glob.glob(os.path.join(root, '*/*/*')):
        arch, subarch, release = resource_path.split('/')[-3:]
        yield (arch, subarch, release)


BOOTLOADERS = ['pxelinux.0', 'chain.c32', 'ifcpu64.c32']

BOOTLOADER_DIR = '/usr/lib/syslinux'


def install_boot_loaders(destination):
    """Install the bootloaders into the specified directory.

    The already-present bootloaders are left untouched.

    :param destination: Directory where the loaders should be stored.
    """
    for bootloader in BOOTLOADERS:
        bootloader_src = os.path.join(BOOTLOADER_DIR, bootloader)
        bootloader_dst = os.path.join(destination, bootloader)
        install_bootloader(bootloader_src, bootloader_dst)


def main():

    try:
        config = Config.load_from_cache()
    except IOError as e:
        if e.errno != errno.ENOENT:
            raise
        config = Config.get_defaults()

    storage = config['boot']['storage']

    boot = create_empty_hierarchy()
    dumper = RepoDumper()

    for source in reversed(config['boot']['sources']):
        repo_boot = dumper.dump(source['path'])
        boot_merge(boot, repo_boot, source['selections'])

    meta = jsondumps(boot)
    current_meta = storage + '/current/maas.meta'
    if os.path.isfile(current_meta) and meta == open(current_meta).read():
        return

    snapshot_name = '/snapshot-%s/' % datetime.now().strftime('%d%m%Y-%H%M%S')
    snapshot_path = storage + snapshot_name
    reverse_boot = boot_reverse(boot)
    writer = RepoWriter(snapshot_path, storage + '/cache/', reverse_boot)

    for source in config['boot']['sources']:
        writer.write(source['path'])

    open(snapshot_path + '/maas.meta', 'w').write(meta)
    symlink_path = storage + '/current'
    if os.path.lexists(symlink_path):
        os.unlink(symlink_path)
    os.symlink(snapshot_path, symlink_path)

    with open(snapshot_path + '/maas.tgt', 'w') as output:
        for arch, subarch, release in available_boot_resources(snapshot_path):
            disk = os.path.join(snapshot_path, arch, subarch, release, 'disk')
            if os.path.isfile(disk):
                output.write(tgt_entry(arch, subarch, release, disk))

    call_and_check(['tgt-admin', '--update', 'ALL'])

    install_boot_loaders(snapshot_path)
