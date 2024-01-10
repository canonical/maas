# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Simplestreams code to download boot resources."""


from datetime import datetime
import os.path
import tarfile

from simplestreams.mirrors import BasicMirrorWriter, UrlMirrorReader
from simplestreams.objectstores import FileStore
from simplestreams.util import (
    item_checksums,
    path_from_mirror_url,
    products_exdata,
)

from maasserver.import_images.helpers import (
    get_os_from_product,
    get_signing_policy,
    maaslog,
)
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


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
    log.debug(
        "Inserting file {name} (tag={tag}, size={size}).",
        name=name,
        tag=tag,
        size=size,
    )
    store.insert(tag, content_source, checksums, mutable=False, size=size)
    # XXX jtv 2014-04-24 bug=1313580: Isn't _fullpath meant to be private?
    return [(store._fullpath(tag), name)]


def extract_archive_tar(store, name, tag, checksums, size, content_source):
    """Extract an archive.tar.xz into `store`.

    :param store: A simplestreams `ObjectStore`.
    :param name: Logical name of the file being inserted.  Only needs to be
        unique within the scope of this boot image.
    :param tag: UUID, or "tag," for the file archive.tar.xz file. The
        archive.tar.xz file along with its contents will be stored in the
        cache directory under names derived from this tag.
    :param checksums: A Simplestreams checksums dict, mapping hash algorihm
        names (such as `sha256`) to the file's respective checksums as
        computed by those hash algorithms.
    :param size: Optional size for the file, so Simplestreams knows what size
        to expect.
    :param content_source: A Simplestreams `ContentSource` for reading the
        file.
    :return: A list of inserted files (file and archive.tar.xz) described
        as tuples of (path, logical name).  The path lies in the directory
        managed by `store` and has a filename based on `tag`, not logical name.
    """
    log.debug(
        "Inserting archive {name} (tag={tag}, size={size}).",
        name=name,
        tag=tag,
        size=size,
    )
    extracted_files = []
    cache_dir = store._fullpath("")
    # Check if the archive has already been extracted. This is done by scanning
    # the cache directory for files containing the given tag. Since the tag is
    # the SHA256 this will always be unique and if files are added/removed from
    # the archive we'll get a new tag.
    for root, dirs, files in os.walk(cache_dir):
        for f in files:
            if f.endswith(tag):
                # Strip out the tag
                filename = f[: -(len(tag) + 1)]
                if root != cache_dir:
                    filename = os.path.join(root[len(cache_dir) :], filename)
                # Give full path to cached file
                filepath = os.path.join(root, f)
                extracted_files.append((filepath, filename))

    # If no files with the given tag were found we need to extract them.
    if extracted_files == []:
        log.debug(
            "Extracting archive {name} (tag={tag}, size={size}).",
            name=name,
            tag=tag,
            size=size,
        )
        archive_path = store._fullpath(tag)
        store.insert(tag, content_source, checksums, mutable=False, size=size)
        with tarfile.open(archive_path, "r|*") as tar:
            for member in tar:
                if member.isfile():
                    filename = member.name
                    filepath = store._fullpath(f"{filename}-{tag}")
                    fo = tar.extractfile(member)
                    store.insert(filepath, fo, mutable=False)
                    extracted_files.append((filepath, filename))
        store.remove(tag)

    # Return the list of sets containing the path to the cache file and the
    # real filename which should be used.
    return extracted_files


def link_resources(
    snapshot_path,
    links,
    osystem,
    arch,
    release,
    label,
    subarches,
    bootloader_type=None,
):
    """Hardlink entries in the snapshot directory to resources in the cache.

    This creates file entries in the snapshot directory for boot resources
    that are part of a single boot image.

    :param snapshot_path: Snapshot directory.
    :param links: A list of links that should be created to files stored in
        the cache.  Each link is described as a tuple of (path, logical
        name).  The path points to a file in the cache directory.  The logical
        name will be link's filename, without path.
    :param osystem: Operating system with this boot image supports.
    :param arch: Architecture which this boot image supports.
    :param release: OS release of which this boot image is a part.
    :param label: OS release label of which this boot image is a part, e.g.
        `release` or `rc`.
    :param subarches: A list of sub-architectures which this boot image
        supports.  For example, a kernel for one Ubuntu release for a given
        architecture and subarchitecture `generic` will typically also support
        the `hwe-*` subarchitectures that denote hardware-enablement kernels
        for older Ubuntu releases.
    :param bootloader_type: If the resource is a bootloader specify the type of
        bootloader(pxe, uefi, open-firmware). Bootloader resources are linked
        under a base 'bootloader' directory instead of the image path.
    """
    for subarch in subarches:
        if bootloader_type is None:
            directory = os.path.join(
                snapshot_path, osystem, arch, subarch, release, label
            )
        else:
            # Subarches are only supported on Ubuntu. With the path bootloaders
            # are being put in below having multiple subarches on a bootloader
            # will cause the contents from one subarch to overwrite the
            # contents of another.
            assert len(subarches) == 1
            directory = os.path.join(
                snapshot_path, "bootloader", bootloader_type, arch
            )
        if not os.path.exists(directory):
            os.makedirs(directory)
        for cached_file, logical_name in links:
            link_path = os.path.join(directory, logical_name)
            if os.path.isfile(link_path):
                os.remove(link_path)
            base_dir = os.path.dirname(link_path)
            if not os.path.exists(base_dir):
                os.makedirs(base_dir)
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
        super().__init__(
            config={
                # Only download the latest version. Without this all versions
                # will be downloaded from simplestreams.
                "max_items": 1
            }
        )

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
        tag = checksums["sha256"]
        size = data["size"]
        ftype = item["ftype"]
        filename = os.path.basename(item["path"])
        if ftype == "archive.tar.xz":
            links = extract_archive_tar(
                self.store, filename, tag, checksums, size, contentsource
            )
        else:
            links = insert_file(
                self.store, filename, tag, checksums, size, contentsource
            )

        osystem = get_os_from_product(item)

        # link_resources creates a hardlink for every subarch. Every Ubuntu
        # product in a SimpleStream contains a list of subarches which list
        # what subarches are a subset of that subarch. For example Xenial
        # ga-16.04 has the subarches list hwe-{p,q,r,s,t,u,v,w},ga-16.04.
        # Kernel flavors are the same arch, the only difference is the kernel
        # config. So ga-16.04-lowlatency has the same subarch list as ga-16.04.
        # If we create hard links for all subarches a kernel flavor may
        # overwrite the generic kernel hard link. This happens if a kernel
        # flavor is processed after the generic kernel. Since MAAS doesn't use
        # the other hard links only create hard links for the subarch of the
        # product we have and a rolling link if it's a rolling kernel.
        if "subarch" in item:
            # MAAS uses the 'generic' subarch when it doesn't know which
            # subarch to use. This happens during enlistment and commissioning.
            # Allow the 'generic' kflavor to own the 'generic' hardlink. The
            # generic kernel should always be the ga kernel for xenial+,
            # hwe-<first letter of release> for older releases.
            if item.get("kflavor") == "generic" and (
                item["subarch"].startswith("ga-")
                or item["subarch"] == "hwe-%s" % item["release"][0]
            ):
                subarches = {item["subarch"], "generic"}
            else:
                subarches = {item["subarch"]}
        else:
            subarches = {"generic"}

        if item.get("rolling", False):
            subarch_parts = item["subarch"].split("-")
            subarch_parts[1] = "rolling"
            subarches.add("-".join(subarch_parts))
        link_resources(
            snapshot_path=self.root_path,
            links=links,
            osystem=osystem,
            arch=item["arch"],
            release=item["release"],
            label=item["label"],
            subarches=subarches,
            bootloader_type=item.get("bootloader-type"),
        )


def download_boot_resources(
    path, store, snapshot_path, product_mapping, keyring_file=None
):
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
    maaslog.info("Downloading boot resources from %s", path)
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
    snapshot_name = "snapshot-%s" % now.strftime("%Y%m%d-%H%M%S")
    return os.path.join(storage_path, snapshot_name)


def download_all_boot_resources(
    sources, storage_path, product_mapping, store=None
):
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
    # Use a FileStore as our ObjectStore implementation.  It will write to the
    # cache directory.
    if store is None:
        cache_path = os.path.join(storage_path, "cache")
        store = FileStore(cache_path)
    # XXX jtv 2014-04-11: FileStore now also takes an argument called
    # complete_callback, which can be used for progress reporting.

    for source in sources:
        download_boot_resources(
            source["url"],
            store,
            snapshot_path,
            product_mapping,
            keyring_file=source.get("keyring"),
        ),

    return snapshot_path
