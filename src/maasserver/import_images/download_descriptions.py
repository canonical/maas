# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Download boot resource descriptions from Simplestreams repo.

This module is responsible only for syncing the repo's metadata, not the boot
resources themselves.  The two are handled in separate Simplestreams
synchronisation stages.
"""

from typing import Any, Iterable

from maasserver.sqlalchemy import service_layer
from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping


def value_passes_filter_list(filter_list, property_value):
    """Does the given property of a boot image pass the given filter list?

    The value passes if either it matches one of the entries in the list of
    filter values, or one of the filter values is an asterisk (`*`).
    """
    return "*" in filter_list or property_value in filter_list


def value_passes_filter(filter_value, property_value):
    """Does the given property of a boot image pass the given filter?

    The value passes the filter if either the filter value is an asterisk
    (`*`) or the value is equal to the filter value.
    """
    return filter_value in ("*", property_value)


def image_passes_filter(filters, os, arch, subarch, release, label):
    """Filter a boot image against configured import filters.

    :param filters: A list of dicts describing the filters, as in `boot_merge`.
        If the list is empty, or `None`, any image matches.  Any entry in a
        filter may be a string containing just an asterisk (`*`) to denote that
        the entry will match any value.
    :param os: The given boot image's operating system.
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
            value_passes_filter(filter_dict["os"], os)
            and value_passes_filter(filter_dict["release"], release)
            and value_passes_filter_list(filter_dict["arches"], arch)
            and value_passes_filter_list(filter_dict["subarches"], subarch)
            and value_passes_filter_list(filter_dict["labels"], label)
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
    :param filters: List of dicts, each of which contains 'os', arch',
        'subarch', 'release', and 'label' keys.  If given, entries are only
        considered for copying from `additions` to `destination` if they match
        at least one of the filters.  Entries in the filter may be the string
        `*` (or for entries that are lists, may contain the string `*`) to make
        them match any value.
    """
    for image, resource in additions.items():
        # Cannot filter by kflavor so it is excluded in the filtering.
        os, arch, subarch, _, release, label = image
        if image_passes_filter(filters, os, arch, subarch, release, label):
            # Do not override an existing entry with the same
            # os/arch/subarch/release/label: the first entry found takes
            # precedence.
            destination.setdefault(image, resource)


def download_all_image_descriptions(
    sources: Iterable[dict[str, Any]],
    validate_products: bool = True,
) -> BootImageMapping:
    """Download image metadata for all sources in `config`.

    :param sources: An iterable of the sources whose keyrings need to be
        written.
    :param validate_products: Whether to validate products in the boot
        sources.
    :return: A populated boot image mapping from the provided sources.
    """
    boot = BootImageMapping()
    for source in sources:
        repo_boot = service_layer.services.boot_sources.fetch(
            source["url"],
            keyring_path=source.get("keyring", None),
            keyring_data=source.get("keyring_data", None),
            validate_products=validate_products,
        )

        boot_merge(boot, repo_boot, source["selections"])
    return boot
