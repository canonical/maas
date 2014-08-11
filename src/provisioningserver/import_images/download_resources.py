# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Simplestreams code to download boot resources."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'download_all_boot_resources',
    ]

from datetime import datetime
from gzip import GzipFile
import os.path

from provisioningserver.import_images.helpers import (
    get_signing_policy,
    maaslog,
    )
from provisioningserver.utils.shell import call_and_check
from simplestreams.contentsource import FdContentSource
from simplestreams.mirrors import (
    BasicMirrorWriter,
    UrlMirrorReader,
    )
from simplestreams.objectstores import FileStore
from simplestreams.util import (
    item_checksums,
    path_from_mirror_url,
    products_exdata,
    )


DEFAULT_KEYRING_PATH = "/usr/share/keyrings"


def insert_file(store, name, tag, checksums, size, content_source):
    """Insert a file into `store`.

    :param store: A simplestreams `ObjectStore`.
    :param name: Logical name of the file being inserted.  Only needs to be
        unique within the scope of this boot image.
    :param tag: UUID, or "tag," for the file.  It will be inserted into
        `store` under this name, not its logical name.
    :param checksums: A Simplestreams checksums dict, mapping hash algorihm
        names (such as `sha256`) to the file's respective checksums as
        computed by those hash algorithms.
    :param size: Optional size for the file, so Simplestreams knows what size
        to expect.
    :param content_source: A Simplestreams `ContentSource` for reading the
        file.
    :return: A list of inserted files (actually, only the one file in this
        case) described as tuples of (path, logical name).  The path lies in
        the directory managed by `store` and has a filename based on `tag`,
        not logical name.
    """
    maaslog.debug("Inserting file %s (tag=%s, size=%s).", name, tag, size)
    store.insert(tag, content_source, checksums, mutable=False, size=size)
    # XXX jtv 2014-04-24 bug=1313580: Isn't _fullpath meant to be private?
    return [(store._fullpath(tag), name)]


def call_uec2roottar(root_image_path, root_tgz_path):
    """Invoke `uec2roottar` with the given arguments.

    Here only so tests can stub it out.

    :param root_image_path: Input file.
    :param root_tgz_path: Output file.
    """
    call_and_check([
        'sudo', '/usr/bin/uec2roottar',
        '--user=maas',
        root_image_path,
        root_tgz_path,
        ])


def insert_root_image(store, tag, checksums, size, content_source):
    """Insert a root image into `store`.

    This may involve converting a UEC boot image into a root tarball.

    :param store: A simplestreams `ObjectStore`.
    :param tag: UUID, or "tag," for the file root image file.  The root image
        and root tarball will both be stored in the cache directory under
        names derived from this tag.
    :param checksums: A Simplestreams checksums dict, mapping hash algorihm
        names (such as `sha256`) to the file's respective checksums as
        computed by those hash algorithms.
    :param size: Optional size for the file, so Simplestreams knows what size
        to expect.
    :param content_source: A Simplestreams `ContentSource` for reading the
        file.
    :return: A list of inserted files (root image and root tarball) described
        as tuples of (path, logical name).  The path lies in the directory
        managed by `store` and has a filename based on `tag`, not logical name.
    """
    maaslog.debug("Inserting root image (tag=%s, size=%s).", tag, size)
    root_image_tag = 'root-image-%s' % tag
    # XXX jtv 2014-04-24 bug=1313580: Isn't _fullpath meant to be private?
    root_image_path = store._fullpath(root_image_tag)
    root_tgz_tag = 'root-tgz-%s' % tag
    root_tgz_path = store._fullpath(root_tgz_tag)
    if not os.path.isfile(root_image_path):
        maaslog.debug("New root image: %s.", root_image_path)
        store.insert(tag, content_source, checksums, mutable=False, size=size)
        uncompressed = FdContentSource(GzipFile(store._fullpath(tag)))
        store.insert(root_image_tag, uncompressed, mutable=False)
        store.remove(tag)
    if not os.path.isfile(root_tgz_path):
        maaslog.debug("Converting root tarball: %s.", root_tgz_path)
        call_uec2roottar(root_image_path, root_tgz_path)
    return [(root_image_path, 'root-image'), (root_tgz_path, 'root-tgz')]


def link_resources(snapshot_path, links, arch, release, label, subarches):
    """Hardlink entries in the snapshot directory to resources in the cache.

    This creates file entries in the snapshot directory for boot resources
    that are part of a single boot image.

    :param snapshot_path: Snapshot directory.
    :param links: A list of links that should be created to files stored in
        the cache.  Each link is described as a tuple of (path, logical
        name).  The path points to a file in the cache directory.  The logical
        name will be link's filename, without path.
    :param arch: Architecture which this boot image supports.
    :param release: OS release of which this boot image is a part.
    :param label: OS release label of which this boot image is a part, e.g.
        `release` or `rc`.
    :param subarches: A list of sub-architectures which this boot image
        supports.  For example, a kernel for one Ubuntu release for a given
        architecture and subarchitecture `generic` will typically also support
        the `hwe-*` subarchitectures that denote hardware-enablement kernels
        for older Ubuntu releases.
    """
    for subarch in subarches:
        directory = os.path.join(snapshot_path, arch, subarch, release, label)
        if not os.path.exists(directory):
            os.makedirs(directory)
        for cached_file, logical_name in links:
            link_path = os.path.join(directory, logical_name)
            if os.path.isfile(link_path):
                os.remove(link_path)
            os.link(cached_file, link_path)


class RepoWriter(BasicMirrorWriter):
    """Download boot resources from an upstream Simplestreams repo.

    :ivar root_path: Snapshot directory.
    :ivar store: A simplestreams `ObjectStore` where downloaded resources
        should be stored.
    :ivar product_mapping: A `ProductMapping` describing the desired boot
        resources.
    """

    def __init__(self, root_path, store, product_mapping):
        self.root_path = root_path
        self.store = store
        self.product_mapping = product_mapping
        super(RepoWriter, self).__init__()

    def load_products(self, path=None, content_id=None):
        """Overridable from `BasicMirrorWriter`."""
        # It looks as if this method only makes sense for MirrorReaders, not
        # for MirrorWriters.  The default MirrorWriter implementation just
        # raises NotImplementedError.  Stop it from doing that.
        return

    def filter_version(self, data, src, target, pedigree):
        """Overridable from `BasicMirrorWriter`."""
        return self.product_mapping.contains(products_exdata(src, pedigree))

    def insert_item(self, data, src, target, pedigree, contentsource):
        """Overridable from `BasicMirrorWriter`."""
        item = products_exdata(src, pedigree)
        checksums = item_checksums(data)
        tag = checksums['sha256']
        size = data['size']
        ftype = item['ftype']
        if ftype == 'root-image.gz':
            links = insert_root_image(
                self.store, tag, checksums, size, contentsource)
        else:
            links = insert_file(
                self.store, ftype, tag, checksums, size, contentsource)

        subarches = self.product_mapping.get(item)
        link_resources(
            snapshot_path=self.root_path, links=links,
            arch=item['arch'], release=item['release'], label=item['label'],
            subarches=subarches)


def download_boot_resources(path, store, snapshot_path, product_mapping,
                            keyring_file=None):
    """Download boot resources for one simplestreams source.

    :param path: The Simplestreams URL for this source.
    :param store: A simplestreams `ObjectStore` where downloaded resources
        should be stored.
    :param snapshot_path: Filesystem path to a snapshot of current upstream
        boot resources.
    :param product_mapping: A `ProductMapping` describing the resources to be
        downloaded.
    :param keyring_file: Optional path to a keyring file for verifying
        signatures.
    """
    writer = RepoWriter(snapshot_path, store, product_mapping)
    (mirror, rpath) = path_from_mirror_url(path, None)
    policy = get_signing_policy(rpath, keyring_file)
    reader = UrlMirrorReader(mirror, policy=policy)
    writer.sync(reader, rpath)


def compose_snapshot_path(storage_path):
    """Put together a path for a new snapshot.

    A snapshot is a directory in `storage_path` containing boot resources.
    The snapshot's name contains the date in a sortable format.

    :param storage_path: Root storage directory,
        usually `/var/lib/maas/boot-resources`.
    :return: Path to the snapshot directory.
    """
    now = datetime.utcnow()
    snapshot_name = 'snapshot-%s' % now.strftime('%Y%m%d-%H%M%S')
    return os.path.join(storage_path, snapshot_name)


def download_all_boot_resources(
        sources, storage_path, product_mapping, store=None):
    """Download the actual boot resources.

    Local copies of boot resources are downloaded into a "cache" directory.
    This is a raw, flat store of resources, with UUID-based filenames called
    "tags."

    In addition, the downlads are hardlinked into a "snapshot directory."  This
    directory, named after the date and time that the snapshot was initiated,
    reflects the currently available boot resources in a proper directory
    hierarchy with subdirectories for architectures, releases, and so on.

    :param sources: List of dicts describing the Simplestreams sources from
        which we should download.
    :param storage_path: Root storage directory,
        usually `/var/lib/maas/boot-resources`.
    :param snapshot_path:
    :param product_mapping: A `ProductMapping` describing the resources to be
        downloaded.
    :param store: A `FileStore` instance. Used only for testing.
    :return: Path to the snapshot directory.
    """
    storage_path = os.path.abspath(storage_path)
    snapshot_path = compose_snapshot_path(storage_path)
    ubuntu_path = os.path.join(snapshot_path, 'ubuntu')
    # Use a FileStore as our ObjectStore implementation.  It will write to the
    # cache directory.
    if store is None:
        cache_path = os.path.join(storage_path, 'cache')
        store = FileStore(cache_path)
    # XXX jtv 2014-04-11: FileStore now also takes an argument called
    # complete_callback, which can be used for progress reporting.

    for source in sources:
        download_boot_resources(
            source['url'], store, ubuntu_path, product_mapping,
            keyring_file=source.get('keyring')),

    return snapshot_path
