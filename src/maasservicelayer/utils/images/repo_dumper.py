# Copyright 2014-2025 Canonical Ltd. This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Download boot resource descriptions from Simplestreams repo.

This module is responsible only for syncing the repo's metadata, not the boot
resources themselves.  The two are handled in separate Simplestreams
synchronisation stages.
"""

import re

from simplestreams import util as sutil
from simplestreams.mirrors import BasicMirrorWriter, UrlMirrorReader
from simplestreams.util import products_exdata
import structlog

from maasservicelayer.utils.images.boot_image_mapping import BootImageMapping
from maasservicelayer.utils.images.helpers import (
    get_os_from_product,
    ImageSpec,
)

logger = structlog.getLogger()

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


def clean_up_repo_item(item: dict[str, str]) -> dict[str, str]:
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


def validate_ubuntu(data: dict[str, str], product_name: str) -> bool:
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


def validate_bootloader(data: dict[str, str], product_name: str) -> bool:
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


def validate_product(data: dict[str, str], product_name: str) -> bool:
    return validate_ubuntu(data, product_name) and validate_bootloader(
        data, product_name
    )


class RepoDumper(BasicMirrorWriter):
    """Gather metadata about boot images available in a Simplestreams repo.

    Used inside `BootSourcesService::fetch`.  Stores basic metadata about
    each image it finds upstream in a given `BootImageMapping`.  Each stored
    item is a dict containing the basic metadata for retrieving a boot image.

    Simplestreams' `BasicMirrorWriter` in itself is stateless.  It relies on
    a subclass (such as this one) to store data.

    :ivar boot_images_dict: A `BootImageMapping`.  Image metadata will be
        stored here as it is discovered.  Simplestreams does not interact with
        this variable.
    """

    def __init__(
        self,
        boot_images_dict: BootImageMapping,
        validate_products: bool = True,
    ):
        super().__init__(
            config={
                # Only download the latest version. Without this all versions
                # will be read, causing miss matches in versions.
                "max_items": 1
            }
        )
        self.boot_images_dict = boot_images_dict
        self.validate_products = validate_products

    def load_products(self, path=None, content_id=None) -> None:
        """Overridable from `BasicMirrorWriter`."""
        # It looks as if this method only makes sense for MirrorReaders, not
        # for MirrorWriters.  The default MirrorWriter implementation just
        # raises NotImplementedError.  Stop it from doing that.
        return

    def insert_item(self, data, src, target, pedigree, contentsource) -> None:
        """Overridable from `BasicMirrorWriter`."""
        item = products_exdata(src, pedigree)
        if self.validate_products and not validate_product(item, pedigree[0]):
            logger.warning(f"Ignoring unsupported product {pedigree[0]}")
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

            # HWE resources need to map to a specific resource, and not just to
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
                hwe_archs = [f"ga-{item['version']}", f"hwe-{release[0]}"]
                if subarch in hwe_archs and "generic" in subarches:
                    self.boot_images_dict.set(
                        base_image._replace(subarch="generic"), compact_item
                    )

    def sync(self, reader: UrlMirrorReader, path: str) -> None:
        try:
            super().sync(reader, path)
        except OSError:
            logger.warning(
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
            logger.error(
                "Failed to download image descriptions with Simplestreams "
                "(%s). Verify network connectivity." % error
            )
            raise
