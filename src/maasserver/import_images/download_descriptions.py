# Copyright 2014-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Download boot resource descriptions from Simplestreams repo.

This module is responsible only for syncing the repo's metadata, not the boot
resources themselves.  The two are handled in separate Simplestreams
synchronisation stages.
"""

import re

from simplestreams import util as sutil
from simplestreams.mirrors import BasicMirrorWriter, UrlMirrorReader
from simplestreams.util import path_from_mirror_url, products_exdata

from maasserver.import_images.boot_image_mapping import BootImageMapping
from maasserver.import_images.helpers import (
    get_os_from_product,
    get_signing_policy,
    ImageSpec,
    maaslog,
)

# Compile a regex to validate Ubuntu product names. This only allows V2 and V3
# Ubuntu images. "v3+platform" is intended for platform-optimised kernels.
UBUNTU_REGEX = re.compile(r".*:v([23]|3\+platform):.*", re.IGNORECASE)
# Compile a regex to validate Ubuntu Core. By having 'v4' in the
# product name it is prevented from being shown in older versions of
# MAAS which do not support Ubuntu Core.
UBUNTU_CORE_REGEX = re.compile(".*:v4:.*", re.IGNORECASE)
# Compile a regex to validate bootloader product names. This only allows V1
# bootloaders.
BOOTLOADER_REGEX = re.compile(".*:1:.*", re.IGNORECASE)


def clean_up_repo_item(item):
    """Return a subset of dict `item` for storing in a boot images dict."""
    keys_to_keep = [
        "content_id",
        "product_name",
        "version_name",
        "path",
        "subarches",
        "release_codename",
        "release_title",
        "support_eol",
        "kflavor",
        "bootloader-type",
        "os_title",
        "gadget_title",
    ]
    compact_item = {key: item[key] for key in keys_to_keep if key in item}
    return compact_item


def validate_ubuntu(data, product_name):
    osystem = data.get("os", "")
    if "ubuntu" not in osystem.lower():
        # It's not an Ubuntu product, nothing to validate.
        return True
    elif (
        osystem == "ubuntu-core"
        and UBUNTU_CORE_REGEX.search(product_name) is not None
    ):
        return True
    elif UBUNTU_REGEX.search(product_name) is None:
        # Only insert v2 or v3 Ubuntu products.
        return False
    else:
        return True


def validate_bootloader(data, product_name):
    bootloader_type = data.get("bootloader-type")
    if bootloader_type is None:
        # It's not a bootloader, nothing to validate
        return True
    if BOOTLOADER_REGEX.search(product_name) is None:
        # Only insert V1 bootloaders from the stream
        return False
    # Validate MAAS supports the specific bootloader_type, os, arch
    # combination.
    SUPPORTED_BOOTLOADERS = {
        "pxe": [{"os": "pxelinux", "arch": "i386"}],
        "uefi": [
            {"os": "grub-efi-signed", "arch": "amd64"},
            {"os": "grub-efi", "arch": "arm64"},
        ],
        "open-firmware": [{"os": "grub-ieee1275", "arch": "ppc64el"}],
    }
    for bootloader in SUPPORTED_BOOTLOADERS.get(bootloader_type, []):
        if (
            data.get("os") == bootloader["os"]
            and data.get("arch") == bootloader["arch"]
        ):
            return True

    # Bootloader not supported, ignore
    return False


def validate_product(data, product_name):
    return validate_ubuntu(data, product_name) and validate_bootloader(
        data, product_name
    )


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

    def __init__(self, boot_images_dict, validate_products=True):
        super().__init__(
            config={
                # Only download the latest version. Without this all versions
                # will be read, causing miss matches in versions.
                "max_items": 1
            }
        )
        self.boot_images_dict = boot_images_dict
        self.validate_products = validate_products

    def load_products(self, path=None, content_id=None):
        """Overridable from `BasicMirrorWriter`."""
        # It looks as if this method only makes sense for MirrorReaders, not
        # for MirrorWriters.  The default MirrorWriter implementation just
        # raises NotImplementedError.  Stop it from doing that.
        return

    def insert_item(self, data, src, target, pedigree, contentsource):
        """Overridable from `BasicMirrorWriter`."""
        item = products_exdata(src, pedigree)
        if self.validate_products and not validate_product(item, pedigree[0]):
            maaslog.warning("Ignoring unsupported product %s" % pedigree[0])
            return
        os = get_os_from_product(item)
        arch = item["arch"]
        subarches = item.get("subarches", "generic")
        if item.get("bootloader-type") is None:
            release = item["release"]
            kflavor = item.get("kflavor", "generic")
        else:
            release = item["bootloader-type"]
            kflavor = "bootloader"
        label = item["label"]
        base_image = ImageSpec(os, arch, None, kflavor, release, label)
        compact_item = clean_up_repo_item(item)

        if os == "ubuntu-core":
            # For Ubuntu Core we only want one entry per release/arch/gadget
            gadget = item.get("gadget_snap", "generic")
            kflavor = item.get("kernel_snap", "generic")
            release = f"{release}-{gadget}"
            self.boot_images_dict.setdefault(
                base_image._replace(
                    subarch="generic", kflavor=kflavor, release=release
                ),
                compact_item,
            )
        else:
            for subarch in subarches.split(","):
                self.boot_images_dict.setdefault(
                    base_image._replace(subarch=subarch), compact_item
                )

            # HWE resources need to map to a specfic resource, and not just to
            # any of the supported subarchitectures for that resource.
            subarch = item.get("subarch", "generic")
            self.boot_images_dict.set(
                base_image._replace(subarch=subarch), compact_item
            )

            if os == "ubuntu" and item.get("version") is not None:
                # HWE resources with generic, should map to the HWE that ships
                # with that release. Starting with Xenial kernels changed from
                # using the naming format hwe-<letter> to ga-<version>. Look
                # for both.
                hwe_archs = ["ga-%s" % item["version"], "hwe-%s" % release[0]]
                if subarch in hwe_archs and "generic" in subarches:
                    self.boot_images_dict.set(
                        base_image._replace(subarch="generic"), compact_item
                    )

    def sync(self, reader: UrlMirrorReader, path: str) -> None:
        try:
            super().sync(reader, path)
        except OSError:
            maaslog.warning(
                "I/O error while syncing boot images. If this problem "
                "persists, verify network connectivity and disk usage."
            )
            # This MUST NOT suppress the I/O error because callers use
            # self.boot_images_dict as the "return" value. Suppressing
            # exceptions here gives the caller no reason to doubt that
            # boot_images_dict is not utter garbage and so pass it up the
            # stack where it is then acted upon, to empty out BootSourceCache
            # for example. True story.
            raise
        except sutil.SignatureMissingException as error:
            # Handle this error here so we can log for both the region and rack
            # have been unable to use simplestreams.
            maaslog.error(
                "Failed to download image descriptions with Simplestreams "
                "(%s). Verify network connectivity." % error
            )
            raise


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


def download_image_descriptions(
    path, keyring=None, user_agent=None, validate_products=True
):
    """Download image metadata from upstream Simplestreams repo.

    :param path: The path to a Simplestreams repo.
    :param keyring: Optional keyring for verifying the repo's signatures.
    :param user_agent: Optional user agent string for downloading the image
        descriptions.
    :return: A `BootImageMapping` describing available boot resources.
    """
    maaslog.info("Downloading image descriptions from %s", path)
    mirror, rpath = path_from_mirror_url(path, None)
    policy = get_signing_policy(rpath, keyring)
    if user_agent is None:
        # If user_agent is NOT set, we know we are downloading descriptions
        # from the Region controller *by* the Rack controller.
        maaslog.info("Rack downloading image descriptions from '%s'.", path)
        reader = UrlMirrorReader(mirror, policy=policy)
    else:
        # Since user_agent is set, we know we are downloading descriptions
        # from the Images repository *by* the Region.
        maaslog.info("Region downloading image descriptions from '%s'.", path)
        try:
            reader = UrlMirrorReader(
                mirror, policy=policy, user_agent=user_agent
            )
        except TypeError:
            # UrlMirrorReader doesn't support the user_agent argument.
            # simplestream >=bzr429 is required for this feature.
            reader = UrlMirrorReader(mirror, policy=policy)

    boot_images_dict = BootImageMapping()
    dumper = RepoDumper(boot_images_dict, validate_products=validate_products)
    dumper.sync(reader, rpath)
    return boot_images_dict


def download_all_image_descriptions(
    sources, user_agent=None, validate_products=True
):
    """Download image metadata for all sources in `config`."""
    boot = BootImageMapping()
    for source in sources:
        repo_boot = download_image_descriptions(
            source["url"],
            keyring=source.get("keyring", None),
            user_agent=user_agent,
            validate_products=validate_products,
        )
        boot_merge(boot, repo_boot, source["selections"])
    return boot
