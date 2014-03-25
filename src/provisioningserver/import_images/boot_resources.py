# Copyright 2013-2014 Canonical Ltd.  This software is licensed under the
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
    'make_arg_parser',
    ]

from argparse import ArgumentParser
from collections import defaultdict
from datetime import datetime
import functools
import glob
from gzip import GzipFile
import json
import logging
from logging import getLogger
import os
from textwrap import dedent

from provisioningserver.config import Config
from provisioningserver.pxe.install_bootloader import install_bootloader
from provisioningserver.pxe.tftppath import list_boot_images
from provisioningserver.utils import (
    atomic_write,
    call_and_check,
    locate_config,
    read_text_file,
    )
from simplestreams.contentsource import FdContentSource
from simplestreams.mirrors import (
    BasicMirrorWriter,
    UrlMirrorReader,
    )
from simplestreams.objectstores import FileStore
from simplestreams.util import (
    item_checksums,
    path_from_mirror_url,
    policy_read_signed,
    products_exdata,
    )


def init_logger():
    logger = getLogger(__name__)
    formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger
import errno


logger = init_logger()


class NoConfigFile(Exception):
    """Raised when the config file for the script doesn't exist."""


def create_empty_hierarchy():
    """Create hierarchy of dicts which supports h[key1]...[keyN] accesses.

    Generated object automatically creates nonexistent levels of hierarchy
    when accessed the following way: h[arch][subarch][release]=something.

    :return Generated hierarchy of dicts.
    """
    return defaultdict(create_empty_hierarchy)


def boot_walk(boot, func):
    """Walk over multi-level depth dict and call callback func for every leaf.

    Function walks over three level depth dictionary organized in a form of
    d[arch][subarch][release]=value and passes control to a callback function
    for each arch/subarch/release triplet available. Stored value is passed
    to a callback function as an additional parameter.

    :param boot: Hierarchy of dicts with a depth equals to three.
    :param func: Callback function f(arch, subarch, release, value).
    """
    for arch in boot:
        for subarch in boot[arch]:
            for release in boot[arch][subarch]:
                for label in boot[arch][subarch][release]:
                    func(
                        arch, subarch, release, label,
                        boot[arch][subarch][release][label])


def value_passes_filter_list(filter_list, property_value):
    """Does the given property of a boot image pass the given filter list?

    The value passes if either it matches one of the entries in the list of
    filter values, or one of the filter values is an asterisk (`*`).
    """
    return '*' in filter_list or property_value in filter_list


def value_passes_filter(filter_value, property_value):
    """Does the given property of a boot image pass the given filter?

    The value passes the filter if either the filter value is an asterisk
    (`*`) or the value is equal to the filter value.
    """
    return filter_value in ('*', property_value)


def image_passes_filter(filters, arch, subarch, release):
    """Filter a boot image against configured import filters.

    :param filters: A list of dicts describing the filters, as in `boot_merge`.
        If the list is empty, or `None`, any image matches.  Any entry in a
        filter may be a string containing just an asterisk (`*`) to denote that
        the entry will match any value.
    :param arch: The given boot image's architecture.
    :param subarch: The given boot image's subarchitecture.
    :param release: The given boot image's OS release.
    :return: Whether the image matches any of the dicts in `filters`.
    """
    # XXX jtv 2014-03-24: add label parameter?
    if filters is None or len(filters) == 0:
        return True
    for filter_dict in filters:
        item_matches = (
            value_passes_filter(filter_dict['release'], release) and
            value_passes_filter_list(filter_dict['arches'], arch) and
            value_passes_filter_list(filter_dict['subarches'], subarch)
        )
        if item_matches:
            return True
    return False


def boot_merge(boot1, boot2, filters=None):
    """Add entries from the second multi-level dict to the first one.

    Function copies d[arch][subarch][release]=value chains from the second
    dictionary to the first one if they don't exist there and pass optional
    check done by filters.

    :param boot1: first dict which will be extended in-place.
    :param boot2: second dict which will be used as a source of new entries.
    :param filters: list of dicts each of which contains 'arch', 'subarch',
        'release' keys; function takes d[arch][subarch][release] chain to the
        first dict only if filters contain at least one dict with
        arch in d['arches'], subarch in d['subarch'], d['release'] == release;
        dict may have '*' as a value for 'arch' and 'release' keys and as a
        member of 'subarch' list -- in that case key-specific check always
        passes.
    """
    def merge_func(arch, subarch, release, label, boot_resource):
        """Merge a boot resource into `boot1`, if it passes filters."""
        if image_passes_filter(filters, arch, subarch, release):
            logger.debug(
                "Merging boot resource for %s/%s/%s/%s.",
                arch, subarch, release, label)
            boot1[arch][subarch][release][label] = boot_resource

    boot_walk(boot2, merge_func)


def boot_reverse(boot):
    """Determine a set of subarches which should be deployed by boot resource.

    Function reverses h[arch][subarch][release]=boot_resource hierarchy to form
    boot resource to subarch relation. Many subarches may be deployed by a
    single boot resource (in which case boot_resource=[subarch1, subarch2]
    relation will be created). We note only subarchitectures and ignore
    architectures because boot resource is tightly coupled with architecture
    it can deploy according to metadata format. We can figure out for which
    architecture we need to use a specific boot resource by looking at its
    description in metadata. We can't do the same with subarch because we may
    want to use boot resource only for a specific subset of subarches it can be
    used for. To represent boot resource to subarch relation we generate the
    following multi-level dictionary: d[content_id][product_name]=[subarches]
    where 'content_id' and 'product_name' values come from metadata information
    and allow us to uniquely identify a specific boot resource.

    :param boot: Hierarchy of dicts d[arch][subarch][release]=boot_resource
    :return Hierarchy of dictionaries d[content_id][product_name]=[subarches]
        which describes boot resource to subarches relation for all available
        boot resources (products).
    """
    reverse = create_empty_hierarchy()

    def reverse_func(arch, subarch, release, label, boot_resource):
        content_id = boot_resource['content_id']
        product_name = boot_resource['product_name']
        existent = list(reverse[content_id][product_name])
        reverse[content_id][product_name] = [subarch] + existent

    boot_walk(boot, reverse_func)
    return reverse


def tgt_entry(arch, subarch, release, label, image):
    """Generate tgt target used to commission arch/subarch with release

    Tgt target used to commission arch/subarch machine with a specific Ubuntu
    release should have the following name: ephemeral-arch-subarch-release.
    This function creates target description in a format used by tgt-admin.
    It uses arch, subarch and release to generate target name and image as
    a path to image file which should be shared. Tgt target is marked as
    read-only. Tgt target has 'allow-in-use' option enabled because this
    script actively uses hardlinks to do image management and root images
    in different folders may point to the same inode. Tgt doesn't allow us to
    use the same inode for different tgt targets (even read-only targets which
    looks like a bug to me) without this option enabled.

    :param arch: Architecture name we generate tgt target for
    :param subarch: Subarchitecture name we generate tgt target for
    :param release: Ubuntu release we generate tgt target for
    :param label: The images' label
    :param image: Path to the image which should be shared via tgt/iscsi
    :return Tgt entry which can be written to tgt-admin configuration file
    """
    prefix = 'iqn.2004-05.com.ubuntu:maas'
    target_name = 'ephemeral-%s-%s-%s-%s' % (arch, subarch, release, label)
    entry = dedent("""\
    <target {prefix}:{target_name}>
        readonly 1
        allow-in-use yes
        backing-store "{image}"
        driver iscsi
    </target>
    """).format(prefix=prefix, target_name=target_name, image=image)
    return entry


def mirror_info_for_path(path, unsigned_policy=None, keyring=None):
    if unsigned_policy is None:
        unsigned_policy = lambda content, path, keyring: content
    (mirror, rpath) = path_from_mirror_url(path, None)
    policy = policy_read_signed
    if rpath.endswith(".json"):
        policy = unsigned_policy
    if keyring:
        policy = functools.partial(policy, keyring=keyring)
    return(mirror, rpath, policy)


class RepoDumper(BasicMirrorWriter):

    def __init__(self):
        super(RepoDumper, self).__init__({'max_items': 1})

    def dump(self, path, keyring=None):
        self._boot = create_empty_hierarchy()
        (mirror, rpath, policy) = mirror_info_for_path(path, keyring=keyring)
        reader = UrlMirrorReader(mirror, policy=policy)
        super(RepoDumper, self).sync(reader, rpath)
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
        label = item['label']
        compact_item = self.item_cleanup(item)
        for subarch in subarches.split(','):
            self._boot[arch][subarch][release][label] = compact_item


class RepoWriter(BasicMirrorWriter):

    def __init__(self, root_path, cache_path, info):
        self._root_path = os.path.abspath(root_path)
        self._info = info
        self._cache = FileStore(os.path.abspath(cache_path))
        super(RepoWriter, self).__init__({'max_items': 1})

    def write(self, path, keyring=None):
        (mirror, rpath, policy) = mirror_info_for_path(path, keyring=keyring)
        reader = UrlMirrorReader(mirror, policy=policy)
        super(RepoWriter, self).sync(reader, rpath)

    def load_products(self, path=None, content_id=None):
        return

    def filter_product(self, data, src, target, pedigree):
        item = products_exdata(src, pedigree)
        content_id, product_name = item['content_id'], item['product_name']
        return (
            content_id in self._info and
            product_name in self._info[content_id]
        )

    def insert_file(self, name, tag, checksums, size, contentsource):
        logger.info("Inserting file %s (tag=%s, size=%s).", name, tag, size)
        self._cache.insert(
            tag, contentsource, checksums, mutable=False, size=size)
        return [(self._cache._fullpath(tag), name)]

    def insert_root_image(self, tag, checksums, size, contentsource):
        root_image_tag = 'root-image-%s' % tag
        root_image_path = self._cache._fullpath(root_image_tag)
        root_tgz_tag = 'root-tgz-%s' % tag
        root_tgz_path = self._cache._fullpath(root_tgz_tag)
        if not os.path.isfile(root_image_path):
            logger.info("New root image: %s.", root_image_path)
            self._cache.insert(
                tag, contentsource, checksums, mutable=False, size=size)
            uncompressed = FdContentSource(
                GzipFile(self._cache._fullpath(tag)))
            self._cache.insert(root_image_tag, uncompressed, mutable=False)
            self._cache.remove(tag)
        if not os.path.isfile(root_tgz_path):
            logger.info("Converting root tarball: %s.", root_tgz_path)
            call_uec2roottar(root_image_path, root_tgz_path)
        return [(root_image_path, 'root-image'), (root_tgz_path, 'root-tgz')]

    def insert_item(self, data, src, target, pedigree, contentsource):
        item = products_exdata(src, pedigree)
        checksums = item_checksums(data)
        tag = checksums['sha256']
        size = data['size']
        ftype = item['ftype']
        if ftype == 'root-image.gz':
            links = self.insert_root_image(tag, checksums, size, contentsource)
        else:
            links = self.insert_file(
                ftype, tag, checksums, size, contentsource)
        for subarch in self._info[item['content_id']][item['product_name']]:
            dst_folder = os.path.join(
                self._root_path, item['arch'], subarch, item['release'],
                item['label'])
            if not os.path.exists(dst_folder):
                os.makedirs(dst_folder)
            for src, link_name in links:
                link_path = os.path.join(dst_folder, link_name)
                if os.path.isfile(link_path):
                    os.remove(link_path)
                os.link(src, link_path)


def available_boot_resources(root):
    for resource_path in glob.glob(os.path.join(root, '*/*/*/*')):
        arch, subarch, release, label = resource_path.split('/')[-4:]
        yield (arch, subarch, release, label)


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


def call_uec2roottar(*args):
    """Invoke `uec2roottar` with the given arguments.

    Here only so tests can stub it out.
    """
    call_and_check(["uec2roottar"] + list(args))


def make_arg_parser(doc):
    """Create an `argparse.ArgumentParser` for this script."""

    parser = ArgumentParser(description=doc)
    default_config = locate_config("bootresources.yaml")
    parser.add_argument(
        '--config-file', action="store", default=default_config,
        help="Path to config file "
             "(defaults to %s)" % default_config)
    return parser


def compose_targets_conf(snapshot_path):
    """Produce the contents of a snapshot's tgt conf file.

    :param snasphot_path: Filesystem path to a snapshot of boot images.
    :return: Contents for a `targets.conf` file.
    :rtype: bytes
    """
    # Use a set to make sure we don't register duplicate entries in tgt.
    entries = set()
    for item in list_boot_images(snapshot_path):
        arch = item['architecture']
        subarch = item['subarchitecture']
        release = item['release']
        label = item['label']
        entries.add((arch, subarch, release, label))
    tgt_entries = []
    for arch, subarch, release, label in sorted(entries):
        root_image = os.path.join(
            snapshot_path, arch, subarch, release, label, 'root-image')
        if os.path.isfile(root_image):
            entry = tgt_entry(arch, subarch, release, label, root_image)
            tgt_entries.append(entry)
    text = ''.join(tgt_entries)
    return text.encode('utf-8')


def meta_contains(storage, content):
    """Does the `maas.meta` file match `content`?

    If the file's contents match the latest data, there is no need to update.
    """
    current_meta = os.path.join(storage, 'current', 'maas.meta')
    return (
        os.path.isfile(current_meta) and
        content == read_text_file(current_meta)
        )


def compose_snapshot_path(storage):
    """Put together a path for a new snapshot.

    A snapshot is a directory in `storage` containing images.  The name
    contains the date in a sortable format.
    """
    snapshot_name = 'snapshot-%s' % datetime.now().strftime('%Y%m%d-%H%M%S')
    return os.path.join(storage, snapshot_name)


def update_current_symlink(storage, latest_snapshot):
    """Symlink `latest_snapshot` as the "current" snapshot."""
    symlink_path = os.path.join(storage, 'current')
    if os.path.lexists(symlink_path):
        os.unlink(symlink_path)
    os.symlink(latest_snapshot, symlink_path)


def write_snapshot_metadata(snapshot, meta_file_content, targets_conf,
                            targets_conf_content):
    """Write "meta" file and tgt config for `snapshot`."""
    meta_file = os.path.join(snapshot, 'maas.meta')
    atomic_write(meta_file_content, meta_file, mode=0644)
    atomic_write(targets_conf_content, targets_conf, mode=0644)


def main(args):
    logger.info("Importing boot resources.")
    # The config file is required.  We do not fall back to defaults if it's
    # not there.
    try:
        config = Config.load_from_cache(filename=args.config_file)
    except IOError as ex:
        if ex.errno == errno.ENOENT:
            # No config file. We have helpful error output for this.
            raise NoConfigFile(ex)
        else:
            # Unexpected error.
            raise

    storage = config['boot']['storage']

    boot = create_empty_hierarchy()
    dumper = RepoDumper()

    for source in reversed(config['boot']['sources']):
        repo_boot = dumper.dump(source['path'], keyring=source['keyring'])
        boot_merge(boot, repo_boot, source['selections'])

    meta_file_content = json.dumps(boot, sort_keys=True)
    if meta_contains(storage, meta_file_content):
        # The current maas.meta already contains the new config.  No need to
        # rewrite anything.
        return

    reverse_boot = boot_reverse(boot)
    snapshot_path = compose_snapshot_path(storage)
    cache_path = os.path.join(storage, 'cache')
    targets_conf = os.path.join(snapshot_path, 'maas.tgt')
    writer = RepoWriter(snapshot_path, cache_path, reverse_boot)

    for source in config['boot']['sources']:
        writer.write(source['path'], source['keyring'])

    targets_conf_content = compose_targets_conf(snapshot_path)

    logger.info("Writing metadata and updating iSCSI targets.")
    write_snapshot_metadata(
        snapshot_path, meta_file_content, targets_conf, targets_conf_content)
    call_and_check(['tgt-admin', '--conf', targets_conf, '--update', 'ALL'])

    logger.info("Installing boot images snapshot %s.", snapshot_path)
    install_boot_loaders(snapshot_path)

    # If we got here, all went well.  This is now truly the "current" snapshot.
    update_current_symlink(storage, snapshot_path)
    logger.info("Import done.")
