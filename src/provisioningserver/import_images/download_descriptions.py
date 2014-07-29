# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Download boot resource descriptions from Simplestreams repo.

This module is responsible only for syncing the repo's metadata, not the boot
resources themselves.  The two are handled in separate Simplestreams
synchronisation stages.
"""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'download_all_image_descriptions',
    ]


from provisioningserver.import_images.boot_image_mapping import (
    BootImageMapping,
    )
from provisioningserver.import_images.helpers import (
    get_signing_policy,
    ImageSpec,
    maaslog,
    )
from simplestreams.mirrors import (
    BasicMirrorWriter,
    UrlMirrorReader,
    )
from simplestreams.util import (
    path_from_mirror_url,
    products_exdata,
    )


def clean_up_repo_item(item):
    """Return a subset of dict `item` for storing in a boot images dict."""
    keys_to_keep = [
        'content_id', 'product_name', 'version_name', 'path', 'subarches']
    compact_item = {key: item[key] for key in keys_to_keep}
    return compact_item


class RepoDumper(BasicMirrorWriter):
    """Gather metadata about boot images available in a Simplestreams repo.

    Used inside `download_image_descriptions`.  Stores basic metadata about
    each image it finds upstream in a given `BootImageMapping`.  Each stored
    item is a dict containing the basic metadata for retrieving a boot image.

    Simplestreams' `BasicMirrorWriter` in itself is stateless.  It relies on
    a subclass (such as this one) to store data.

    :ivar boot_images_dict: A `BootImageMapping`.  Image metadata will be
        stored here as it is discovered.  Simplestreams does not interact with
        this variable.
    """

    def __init__(self, boot_images_dict):
        super(RepoDumper, self).__init__()
        self.boot_images_dict = boot_images_dict

    def load_products(self, path=None, content_id=None):
        """Overridable from `BasicMirrorWriter`."""
        # It looks as if this method only makes sense for MirrorReaders, not
        # for MirrorWriters.  The default MirrorWriter implementation just
        # raises NotImplementedError.  Stop it from doing that.
        return

    def insert_item(self, data, src, target, pedigree, contentsource):
        """Overridable from `BasicMirrorWriter`."""
        item = products_exdata(src, pedigree)
        arch, subarches = item['arch'], item['subarches']
        release = item['release']
        label = item['label']
        base_image = ImageSpec(arch, None, release, label)
        compact_item = clean_up_repo_item(item)
        for subarch in subarches.split(','):
            self.boot_images_dict.setdefault(
                base_image._replace(subarch=subarch), compact_item)


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


def image_passes_filter(filters, arch, subarch, release, label):
    """Filter a boot image against configured import filters.

    :param filters: A list of dicts describing the filters, as in `boot_merge`.
        If the list is empty, or `None`, any image matches.  Any entry in a
        filter may be a string containing just an asterisk (`*`) to denote that
        the entry will match any value.
    :param arch: The given boot image's architecture.
    :param subarch: The given boot image's subarchitecture.
    :param release: The given boot image's OS release.
    :param label: The given boot image's label.
    :return: Whether the image matches any of the dicts in `filters`.
    """
    if filters is None or len(filters) == 0:
        return True
    for filter_dict in filters:
        item_matches = (
            value_passes_filter(filter_dict['release'], release) and
            value_passes_filter_list(filter_dict['arches'], arch) and
            value_passes_filter_list(filter_dict['subarches'], subarch) and
            value_passes_filter_list(filter_dict['labels'], label)
        )
        if item_matches:
            return True
    return False


def boot_merge(destination, additions, filters=None):
    """Complement one `BootImageMapping` with entries from another.

    This adds entries from `additions` (that match `filters`, if given) to
    `destination`, but only for those image specs for which `destination` does
    not have entries yet.

    :param destination: `BootImageMapping` to be updated.  It will be extended
        in-place.
    :param additions: A second `BootImageMapping`, which will be used as a
        source of additional entries.
    :param filters: List of dicts, each of which contains 'arch', 'subarch',
        and 'release' keys.  If given, entries are only considered for copying
        from `additions` to `destination` if they match at least one of the
        filters.  Entries in the filter may be the string `*` (or for entries
        that are lists, may contain the string `*`) to make them match any
        value.
    """
    for image, resource in additions.items():
        arch, subarch, release, label = image
        if image_passes_filter(filters, arch, subarch, release, label):
            maaslog.debug(
                "Merging boot resource for %s/%s/%s/%s.",
                arch, subarch, release, label)
            # Do not override an existing entry with the same
            # arch/subarch/release/label: the first entry found takes
            # precedence.
            destination.setdefault(image, resource)


def download_image_descriptions(path, keyring=None):
    """Download image metadata from upstream Simplestreams repo.

    :param path: The path to a Simplestreams repo.
    :param keyring: Optional keyring for verifying the repo's signatures.
    :return: A `BootImageMapping` describing available boot resources.
    """
    mirror, rpath = path_from_mirror_url(path, None)
    policy = get_signing_policy(rpath, keyring)
    reader = UrlMirrorReader(mirror, policy=policy)
    boot_images_dict = BootImageMapping()
    dumper = RepoDumper(boot_images_dict)
    dumper.sync(reader, rpath)
    if boot_images_dict.is_empty():
        maaslog.warn(
            "No resources found in Simplestreams repository %r.  "
            "Is it correctly configured?",
            path)
    return boot_images_dict


def download_all_image_descriptions(sources):
    """Download image metadata for all sources in `config`."""
    boot = BootImageMapping()
    for source in sources:
        repo_boot = download_image_descriptions(
            source['url'], keyring=source['keyring'])
        boot_merge(boot, repo_boot, source['selections'])
    return boot
