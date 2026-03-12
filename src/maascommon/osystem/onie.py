# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""ONIE Operating System.

ONIE (Open Network Install Environment) is a boot loader for bare metal
network switches that enables OS installation via the network.
"""

from functools import lru_cache
import re

from maascommon.osystem import BOOT_IMAGE_PURPOSE, OperatingSystem

SUPPORTED_VENDORS: frozenset[str] = frozenset(
    [
        "accton",
        "celestica",
        "dell",
        "dellemc",
        "emc",
        "edge-core",
        "mellanox",
        "nvidia",  # Mellanox is now NVIDIA
        "marvell",
        "quanta",
        "supermicro",
    ]
)

RELEASE_PATTERN: re.Pattern[str] = re.compile(
    r"^(?P<vendor>[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)-"
    r"(?P<version>\d+(?:\.\d+)*)$",
    re.IGNORECASE,
)


@lru_cache(maxsize=8)
def parse_release(release: str) -> tuple[str, str] | None:
    """Parse a release string into vendor and version components.

    This function is cached to improve performance when parsing the same
    release strings repeatedly.

    :param release: Release string in format "vendor-version"
    :return: Tuple of (vendor, version) or None if invalid
    """
    match = RELEASE_PATTERN.match(release)
    if match:
        return match.group("vendor").lower(), match.group("version")
    return None


class ONIEOS(OperatingSystem):
    """ONIE operating system for bare metal network switches.

    Handles ONIE images identified by vendor-version format (e.g., mellanox-3.8.0).

    Supported architectures: amd64/generic, arm64/generic, armhf/generic
    Image format: Self-extracting binaries, served as-is without validation
    Purposes: Installation (XINSTALL) only, not commissioning
    """

    name = "onie"
    title = "ONIE"

    def get_boot_image_purposes(self) -> list[str]:
        """Return purposes supported by ONIE images (installation only).

        :return: List containing only XINSTALL purpose.
        """
        return [BOOT_IMAGE_PURPOSE.XINSTALL]

    def get_default_release(self) -> str:
        """Gets the default release to use when a release is not explicit.

        ONIE has no sensible default since the appropriate release depends
        on the specific vendor and model of the switch. This method should
        not be called in practice as ONIE releases must be explicitly specified.

        :return: Empty string (no default)
        """
        return ""

    def get_supported_commissioning_releases(self) -> list[str]:
        """List operating system's supported commissioning releases.

        ONIE does not support commissioning - it's purely for installation.

        :return: Empty list.
        """
        return []

    def get_default_commissioning_release(self) -> str | None:
        """Return operating system's default commissioning release.

        ONIE does not support commissioning.

        :return: None
        """
        return None

    def is_release_supported(self, release: str) -> bool:
        """Check if the given release follows expected naming convention.

        A release is considered valid if it matches the vendor-version pattern.
        Note: MAAS does not validate whether the actual image file is a valid
        ONIE installer - it trusts the user's declaration.

        :param release: Release identifier to check
        :return: True if release format matches expected pattern, False otherwise
        """
        parsed = parse_release(release)
        if not parsed:
            return False

        vendor, version = parsed
        return bool(vendor and version)

    def get_release_title(self, release: str) -> str:
        """Return the title for the given release.

        Converts a release identifier like "mellanox-3.8.0" into a
        human-readable title like "Mellanox ONIE 3.8.0".

        :param release: Release identifier
        :return: Human-readable release title
        """
        parsed = parse_release(release)
        if not parsed:
            return release

        vendor, version = parsed
        vendor_title = self._format_vendor_name(vendor)
        return f"{vendor_title} ONIE {version}"

    def _format_vendor_name(self, vendor: str) -> str:
        """Format vendor name for display.

        :param vendor: Lowercase vendor identifier
        :return: Properly capitalized vendor name
        """
        vendor_names = {
            "dell": "Dell",
            "dellemc": "Dell EMC",
            "emc": "EMC",
            "mellanox": "Mellanox",
            "nvidia": "NVIDIA",
            "accton": "Accton",
            "marvell": "Marvell",
            "edge-core": "Edge-Core",
            "quanta": "Quanta",
            "celestica": "Celestica",
            "supermicro": "Supermicro",
        }
        return vendor_names.get(vendor.lower(), vendor.title())

    def get_supported_vendors(self) -> list[str]:
        """Return list of officially supported ONIE vendors.

        :return: List of vendor identifiers
        """
        return sorted(SUPPORTED_VENDORS)

    def get_vendor_from_release(self, release: str) -> str | None:
        """Extract vendor identifier from a release string.

        :param release: Release string in format "vendor-version"
        :return: Vendor identifier or None if invalid
        """
        parsed = parse_release(release)
        return parsed[0] if parsed else None

    def get_version_from_release(self, release: str) -> str | None:
        """Extract version from a release string.

        :param release: Release string in format "vendor-version"
        :return: Version string or None if invalid
        """
        parsed = parse_release(release)
        return parsed[1] if parsed else None

    def format_release_name(self, vendor: str, version: str) -> str:
        """Create a properly formatted release name from components.

        Note: This validates the naming format only. MAAS does not validate
        whether the actual image file is a valid ONIE installer.

        :param vendor: Vendor identifier (e.g., "mellanox")
        :param version: Version string (e.g., "3.8.0")
        :return: Formatted release name (e.g., "mellanox-3.8.0")
        :raises ValueError: If vendor or version format is invalid
        """
        vendor = vendor.lower().strip()
        version = version.strip()

        if not vendor or not version:
            raise ValueError("Vendor and version must be non-empty")

        if not re.match(r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$", vendor):
            raise ValueError(
                f"Invalid vendor format: {vendor}. "
                "Must be lowercase alphanumeric with optional hyphens."
            )

        if not re.match(r"^\d+(?:\.\d+)*$", version):
            raise ValueError(
                f"Invalid version format: {version}. "
                "Must be digits separated by dots (e.g., 3.8.0)."
            )

        release = f"{vendor}-{version}"

        if not RELEASE_PATTERN.match(release):
            raise ValueError(
                f"Formatted release does not match pattern: {release}"
            )

        return release

    def get_image_filetypes(self) -> dict[str, str]:
        """Return supported file types for ONIE images.

        :return: Dictionary mapping filename patterns to file types
        """
        return {
            "installer.bin": "self-extracting",
        }
