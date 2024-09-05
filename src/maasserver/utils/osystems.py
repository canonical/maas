# Copyright 2014-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).
"""Utilities for working with operating systems."""

__all__ = [
    "get_distro_series_initial",
    "get_release",
    "get_release_requires_key",
    "get_release_version_from_string",
    "list_all_releases_requiring_keys",
    "list_all_usable_hwe_kernels",
    "list_all_usable_osystems",
    "list_commissioning_choices",
    "list_hwe_kernel_choices",
    "list_osystem_choices",
    "list_release_choices",
    "make_hwe_kernel_ui_text",
    "parse_subarch_kernel_string",
    "release_a_newer_than_b",
    "get_working_kernel",
]

from collections import namedtuple
import dataclasses
from operator import attrgetter
from typing import Dict, List

from distro_info import UbuntuDistroInfo
from django.core.exceptions import ValidationError
from django.db.models import Q

from maasserver.enum import BOOT_RESOURCE_FILE_TYPE, BOOT_RESOURCE_TYPE
from maasserver.models import BootResource, BootSourceCache, Config
from maasserver.models.bootresourceset import XINSTALL_TYPES
from provisioningserver.drivers.osystem import OperatingSystemRegistry
from provisioningserver.utils.twisted import undefined


@dataclasses.dataclass
class OSReleaseArchitecture:
    name: str
    image_type: int
    file_type: str

    @property
    def can_deploy_to_memory(self) -> bool:
        if self.image_type == BOOT_RESOURCE_TYPE.SYNCED:
            return self.file_type == BOOT_RESOURCE_FILE_TYPE.SQUASHFS_IMAGE
        else:
            return self.file_type in [
                BOOT_RESOURCE_FILE_TYPE.ROOT_TGZ,
                BOOT_RESOURCE_FILE_TYPE.ROOT_TXZ,
            ]


@dataclasses.dataclass
class OSRelease:
    name: str
    title: str
    alias: str | None = None
    can_commission: bool = False
    requires_license_key: bool = False
    architectures: Dict[str, OSReleaseArchitecture] = dataclasses.field(
        default_factory=dict
    )


@dataclasses.dataclass
class OperatingSystem:
    name: str
    title: str
    default_commissioning_release: str | None = None
    default_release: str = ""
    releases: Dict[str, OSRelease] = dataclasses.field(default_factory=dict)


def list_all_usable_osystems() -> Dict[str, OperatingSystem]:
    """Return all releases for all operating systems that can be used."""
    osystems = {}
    boot_resources = BootResource.objects.filter(bootloader_type=None)
    for br in boot_resources:
        # An OS can have multiple boot resource for one release. e.g Ubuntu
        # Bionic has ga-18.04 and ga-18.04-lowlatency. This list should only
        # contain one entry per OS.

        if "/" in br.name:
            os_name, release_name = br.name.split("/")
        else:
            os_name = "custom"
            release_name = br.name

        if br.alias and "/" in br.alias:
            _, alias_name = br.alias.split("/")
        else:
            alias_name = br.alias

        osystem = OperatingSystemRegistry.get_item(os_name)
        if osystem is not None:
            release_title = osystem.get_release_title(release_name)
            if release_title is None:
                release_title = release_name
            can_commission = (
                release_name in osystem.get_supported_commissioning_releases()
            )
            requires_license_key = osystem.requires_license_key(release_name)
        else:
            release_title = br.name
            can_commission = requires_license_key = False

        if br.rtype == BOOT_RESOURCE_TYPE.UPLOADED:
            # User may set the title of an uploaded resource.
            if "title" in br.extra:
                release_title = br.extra["title"]
            else:
                release_title = release_name

        if os_name not in osystems:
            if osystem is not None:
                default_commissioning_release = (
                    osystem.get_default_commissioning_release()
                )
                default_release = osystem.get_default_release()
                os_title = osystem.title
            else:
                default_commissioning_release = None
                default_release = ""
                os_title = os_name
            osystems[os_name] = OperatingSystem(
                name=os_name,
                title=os_title,
                default_commissioning_release=default_commissioning_release,
                default_release=default_release,
            )
        if release_name not in osystems[os_name].releases:
            osystems[os_name].releases[release_name] = OSRelease(
                name=release_name,
                title=release_title,
                alias=alias_name,
                can_commission=can_commission,
                requires_license_key=requires_license_key,
            )
        latest_set = br.get_latest_set()
        if latest_set is not None:
            resource_files = [
                resource_file
                for resource_file in latest_set.files.all()
                if resource_file.filetype in XINSTALL_TYPES
            ]
            if resource_files:
                osystems[os_name].releases[release_name].architectures[
                    br.architecture
                ] = OSReleaseArchitecture(
                    name=br.architecture,
                    image_type=br.rtype,
                    file_type=resource_files[0].filetype,
                )

    return osystems


def list_osystem_choices(
    osystems: Dict[str, OperatingSystem], include_default: bool = True
):
    """Return Django "choices" list for `osystem`.

    :param include_default: When true includes the 'Default OS' in choice
        selection.
    """
    if include_default:
        choices = [("", "Default OS")]
    else:
        choices = []
    choices += [(osystem.name, osystem.title) for osystem in osystems.values()]
    return sorted(list(set(choices)))


def list_all_usable_hwe_kernels(osystems: Dict[str, OperatingSystem]):
    """Return dictionary of usable `kernels` for each os/release."""
    kernels = {}
    for osystem in osystems.values():
        if osystem.name not in kernels:
            kernels[osystem.name] = {}
        for release in osystem.releases.values():
            os_release = f"{osystem.name}/{release.name}"
            kernels[osystem.name][release.name] = list_hwe_kernel_choices(
                sorted(BootResource.objects.get_kernels(os_release))
            )
            if len(kernels[osystem.name][release.name]) == 0:
                kernels[osystem.name].pop(release.name)
        if len(kernels[osystem.name]) == 0:
            kernels.pop(osystem.name)
    return kernels


def make_hwe_kernel_ui_text(hwe_kernel):
    if not hwe_kernel:
        return hwe_kernel
    # Fall back on getting it from DistroInfo.
    kernel_list = hwe_kernel.split("-")
    if len(kernel_list) >= 2:
        kernel = kernel_list[1]
    else:
        kernel = hwe_kernel
    ubuntu_release = get_release(kernel)
    if ubuntu_release is None:
        return hwe_kernel
    else:
        return "{} ({})".format(ubuntu_release["series"], hwe_kernel)


def list_hwe_kernel_choices(hwe_kernels):
    return [
        (hwe_kernel, make_hwe_kernel_ui_text(hwe_kernel))
        for hwe_kernel in hwe_kernels
    ]


def list_all_releases_requiring_keys(
    osystems: Dict[str, OperatingSystem]
) -> Dict[str, OperatingSystem]:
    """Return dictionary of OS name mapping to `releases` that require
    license keys."""
    distro_series = {}
    for osystem in osystems.values():
        releases = dict(
            (release.name, release)
            for release in osystem.releases.values()
            if release.requires_license_key
        )
        if len(releases) > 0:
            distro_series[osystem.name] = dataclasses.replace(
                osystem,
                releases=releases,
            )
    return distro_series


def get_release_requires_key(release):
    """Return asterisk for any release that requires
    a license key.

    This is used by the JS, to display the licese_key field.
    """
    if release.requires_license_key:
        return "*"
    return ""


def list_release_choices(
    osystems: Dict[str, OperatingSystem],
    include_default: bool = True,
    with_key_required: bool = True,
):
    """Return Django "choices" list for `releases`.

    :param include_default: When true includes the 'Default OS Release' in
        choice selection.
    :param with_key_required: When true includes the release_requires_key in
        the choice.
    """
    if include_default:
        choices = [("", "Default OS Release")]
    else:
        choices = []
    for osystem in sorted(osystems.values(), key=attrgetter("title")):
        for release in sorted(
            osystem.releases.values(), key=attrgetter("title")
        ):
            if with_key_required:
                requires_key = get_release_requires_key(release)
            else:
                requires_key = ""
            choices.append(
                (
                    "{}/{}{}".format(osystem.name, release.name, requires_key),
                    release.title,
                )
            )
    return choices


def get_distro_series_initial(osystems, instance, with_key_required=True):
    """Returns the distro_series initial value for the instance.

    :param with_key_required: When true includes the release_requires_key in
        the choice.
    """
    osystem_name = instance.osystem
    series = instance.distro_series
    osystem = osystems.get(osystem_name)
    if not with_key_required:
        key_required = ""
    elif osystem is not None:
        release = osystem.releases.get(series)
        if release is not None:
            key_required = get_release_requires_key(release)
        else:
            key_required = ""
    else:
        # OS of the instance isn't part of the given OSes list so we can't
        # figure out if the key is required or not, default to not requiring
        # it.
        key_required = ""
    if osystem_name is not None and osystem_name != "":
        if series is None:
            series = ""
        return f"{osystem_name}/{series}{key_required}"
    return None


def list_commissioning_choices(osystems):
    """Return Django "choices" list for releases that can be used for
    commissioning."""
    ubuntu = osystems.get("ubuntu")
    if ubuntu is None:
        return []
    else:
        commissioning_series = Config.objects.get_config(
            name="commissioning_distro_series"
        )
        found_commissioning_series = False
        sorted_releases = sorted(
            ubuntu.releases.values(), key=attrgetter("title")
        )
        releases = []
        for release in sorted_releases:
            if not release.can_commission:
                continue
            if release.name == commissioning_series:
                found_commissioning_series = True
            releases.append((release.name, release.title))
        if found_commissioning_series:
            return releases
        else:
            return [
                (
                    commissioning_series,
                    "%s (No image available)" % commissioning_series,
                )
            ] + releases


def validate_osystem_and_distro_series(osystem, distro_series):
    """Validate `osystem` and `distro_series` are valid choices."""
    if "/" in distro_series:
        series_os, release = distro_series.split("/", 1)
        if series_os != osystem:
            raise ValidationError(
                "%s in distro_series does not match with "
                "operating system %s." % (distro_series, osystem)
            )
    else:
        release = distro_series
    release = release.replace("*", "")
    usable_osystems = list_all_usable_osystems()
    found_osystem = usable_osystems.get(osystem)
    if found_osystem is None:
        raise ValidationError(
            "%s is not a supported operating system." % osystem
        )
    found_release = found_osystem.releases.get(release)
    if found_release is None:
        raise ValidationError(
            "%s/%s is not a supported operating system and release "
            "combination." % (osystem, release)
        )
    return osystem, release


def get_release_from_distro_info(string):
    """Convert an Ubuntu release or version into a release dict.

    This data is pulled from the UbuntuDistroInfo library which contains
    additional information such as the release, EOL, and code name."""
    ubuntu = UbuntuDistroInfo()
    release_found = False
    # We can only look at release names for 12.04+ as previous versions
    # have overlapping first letters(e.g Warty and Wily) which break looking
    # up old style kernels(e.g hwe-w).
    try:
        ubuntu_rows = ubuntu._rows
    except AttributeError:
        ubuntu_rows = [row.__dict__ for row in ubuntu._releases]
    for row in ubuntu_rows:
        if (
            int(row["version"].split(".")[0]) >= 12
            and row["series"].startswith(string)
            or row["version"].startswith(string)
        ):
            release_found = True
            break
    if release_found:
        return row
    else:
        return None


def get_release_from_db(string):
    """Convert an Ubuntu release, version, or subarch into a release dict.

    This does not contain the release, eol, or created dates like
    get_release_from_distro_info does."""
    bsc = BootSourceCache.objects.filter(
        (
            (Q(subarch="hwe-%s" % string) | Q(subarch="ga-%s" % string))
            & (
                Q(release_title__startswith=string)
                | Q(release__startswith=string)
            )
        )
        | Q(release__startswith=string)
        | Q(release_title__startswith=string)
    ).first()
    if bsc is None:
        return None
    elif None in (bsc.release_title, bsc.release, bsc.release_codename):
        return None
    else:
        return {
            "version": bsc.release_title,
            "eol-server": bsc.support_eol,
            "series": bsc.release,
            "codename": bsc.release_codename,
        }


def get_release(string):
    """Convert an Ubuntu release, version, or subarch into a release dict.

    First tries distro_info then falls back on searching SimpleStreams to
    avoid hitting the database. Returns None if not found."""
    release = get_release_from_distro_info(string)
    if not release:
        release = get_release_from_db(string)
    return release


class InvalidSubarchKernelStringError(Exception):
    """Raised when subarch/kernel string does not match
    any of the supported formats"""


ParsedKernelString = namedtuple(
    "ParsedKernelString", ["channel", "release", "platform", "kflavor"]
)


def parse_subarch_kernel_string(kernel_string: str) -> ParsedKernelString:
    """Extracts meaningful info from the 3.4-ish subarch kernel string
    with the following format:
    ```
        [platform-](ga|hwe[-edge])-(release)-[flavour-][edge]
    ```

    This format matches all the older kernel subarches, but also
    allows having the platform specified. Examples of supported strings:
      - `hwe-x`
      - `ga-22.04`
      - `hwe-22.04-lowlatency`
      - `nvidia-ga-22.04`
      - `raspi-hwe-edge-22.04-lowlatency`

    :param kernel_string: kernel subarch string
    :return named tuple (release channel, release, platform, flavour)

    FIXME: This is a workaround for 3.4, it is not intended to become
      a long-term solution (unless we fail spectacularly with improved
      kernel model)
    """
    # Kernel string is dash-separated in this format
    parts = kernel_string.split("-")

    if len(parts) == 1:
        # Legacy format (v1 probably?): subarch is an actual subarch!
        # (now called platform because of "subarch" being abused)
        return ParsedKernelString(
            channel="", release="", platform=kernel_string, kflavor=""
        )

    # Figure out the kernel channel
    channel_index = None
    channels_found = 0
    for possible_channel in ("hwe", "ga"):
        try:
            channel_index = parts.index(possible_channel)
        except ValueError:
            # We expect ValueError
            pass
        else:
            channel = possible_channel
            channels_found += 1
    if channels_found > 1:
        raise InvalidSubarchKernelStringError(
            f"Kernel {kernel_string} has multiple channels specified!"
        )
    if channel_index is None:
        # Once again, subarch is an actual subarch! We don't do that
        # anymore though.
        return ParsedKernelString(
            channel="", release="", platform=kernel_string, kflavor=""
        )

    # Everything before channel is considered as platform
    platform = ""
    if channel_index > 0:
        platform = "-".join(parts[:channel_index])
        parts = parts[channel_index:]

    # HWE channel could be also "hwe-edge", let's check if that is the case
    if channel == "hwe":
        if len(parts) > 1 and parts[1] == "edge":
            channel = "hwe-edge"
            # Get rid of that extra element so that release will be
            # at index 1
            parts = parts[1:]
        elif parts[-1] == "edge":
            channel = "hwe-edge"
            parts = parts[:-1]

    # By this moment we should have release in parts[1] and flavour
    # as the rest of the parts.
    if len(parts) < 2:
        raise ValueError(f"Kernel {kernel_string} has no release specified")
    release = parts[1]
    kflavor = "-".join(parts[2:])
    return ParsedKernelString(
        channel=channel, release=release, platform=platform, kflavor=kflavor
    )


# Coefficients for release sorting in multiple "buckets":
#
# 1. Release name/version only: "warty", "20.04"
# 2. Old-style HWE kernels: "hwe-u", "hwe-x-lowlatency"
# 3. New-style GA kernels
#   3.1 New-style kernels: "ga-20.04"
#   3.2 Flavoured new-style kernels: "ga-22.04-lowlatency"
#   3.3 Platform-optimised kernels: "highbank", "nvidia-ga-22.04"
#   3.4 Platform-optimised flavoured kernels: "nvidia-ga-22.04-lowlatency"
# 4. HWE kernels: same as GA, but with "hwe" instead of "ga" and no "highbank"
# 5. HWE edge kernels: same as HWE
#
HWE_EDGE_CHANNEL_WEIGHT = 10000000
HWE_CHANNEL_WEIGHT = 1000000
PLATFORM_OPTIMISED_WEIGHT = 100000
NEW_STYLE_KERNEL_WEIGHT = 10000
PLATFORM_ONLY_STRING_WEIGHT = NEW_STYLE_KERNEL_WEIGHT
OLD_STYLE_HWE_WEIGHT = 1000
# A small bump for in-bucket priority of non-flavoured kernels
FLAVOURED_WEIGHT = 10


def get_release_version_from_string(
    kernel_string: str,
) -> tuple[int, int, int]:
    """Convert an Ubuntu release, version, or kernel into a version tuple.
    Also calculates "weight" of each release that is used to give
    certain kernels a higher value when compared to other kernels.

    Rolling kernels and releases are given a very high value (999, 999)
    to always be the higher value during comparison.

    :param kernel_string: kernel string to get release version from
    :return Ubuntu version tuple (year, month, weight), where weight
    """
    parts = kernel_string.split("-")
    parts_len = len(parts)
    ubuntu_release = None
    platform = ""
    release = ""
    kflavor = ""
    channel = "ga"
    weight = 0

    # Subarch kernel string parser will treat single-part strings as
    # platforms. For this method, however, we want to also check if
    # the string is a known release name first.
    if kernel_string == "rolling":
        release = "rolling"
    elif parts_len == 1:
        # Might be (always GA):
        # - Just the release name, e.g xenial or 16.04
        # - Single-part-platform, e.g. highbank
        ubuntu_release = get_release(kernel_string)
        if ubuntu_release:
            release = kernel_string
        else:
            platform = kernel_string
            weight += PLATFORM_ONLY_STRING_WEIGHT

    if not (release or platform):
        parsed = parse_subarch_kernel_string(kernel_string)
        channel, release, platform, kflavor = (
            parsed.channel,
            parsed.release,
            parsed.platform,
            parsed.kflavor,
        )

        # hwe kernels should only have a higher weight when using hwe-<version>
        # format. This ensures the old (hwe-{letter}) format maps to the ga kernel.
        if channel == "hwe":
            # `hwe-{letter}` should not get HWE weight bump
            weight += HWE_CHANNEL_WEIGHT if len(release) > 1 else 0
        elif channel == "hwe-edge":
            weight += HWE_EDGE_CHANNEL_WEIGHT
        elif not channel and platform:
            weight += PLATFORM_ONLY_STRING_WEIGHT

    # Old-style HWE strings > release-only strings
    if channel == "hwe" and len(release) == 1:
        weight += OLD_STYLE_HWE_WEIGHT
    # New-style strings > Old-style HWE strings
    elif parts_len > 1 and release:
        weight += NEW_STYLE_KERNEL_WEIGHT

    if release == "rolling":
        # Rolling kernels are always the latest
        version = [999, 999]
    else:
        if release and not ubuntu_release:
            ubuntu_release = get_release(release)
        old_style_platform = not release and platform and platform != "generic"
        if ubuntu_release:
            # Remove 'LTS' from version if it exists
            version = ubuntu_release["version"].split(" ")[0]
            # Convert the version into a list of ints
            version = [int(seg) for seg in version.split(".")]
        elif old_style_platform or parts_len == 1:
            # TODO this is a hack: for an old style platform-specific
            #  kernel, we don't know the version it matches. So we
            #  return the (0, 0) so that the kernel will be returned as
            #  available.
            version = [0, 0]
        else:
            raise ValueError(
                "%s not found amongst the known Ubuntu releases!"
                % kernel_string
            )

    if kflavor and kflavor != "generic":
        weight += FLAVOURED_WEIGHT

    if platform and platform != "generic":
        # Platform-specific kernels should have higher weight over
        # generic ones.
        weight += PLATFORM_OPTIMISED_WEIGHT

    return tuple(version + [weight])


def release_a_newer_than_b(a: str, b: str) -> bool:
    """Compare two Ubuntu releases and return true if a >= b.

    The release names can be the full release name(e.g Precise, Trusty),
    release versions(e.g 12.04, 16.04), or an hwe kernel(e.g hwe-p, hwe-16.04,
    hwe-rolling-lowlatency-edge).
    """
    ver_a = get_release_version_from_string(a)
    ver_b = get_release_version_from_string(b)
    return ver_a >= ver_b


def get_working_kernel(
    requested_kernel: str | None,
    min_compatibility_level: str | None,
    architecture: str,
    osystem: str,
    distro_series: str,
    commissioning_osystem: str | object = undefined,
    commissioning_distro_series: str | object = undefined,
) -> str:
    """Returns ID of kernel that works on the selected os/release/arch.

    Checks that the requested kernel is available for the selected
    os/release/architecture combination, and that the selected hwe_kernel is >=
    min_hwe_kernel. If no hwe_kernel is selected one will be chosen.
    """

    def validate_kernel_str(kstr: str) -> bool:
        ksplit = kstr.split("-")
        return "hwe" in ksplit or "ga" in ksplit

    if not all((osystem, architecture, distro_series)):
        return requested_kernel

    arch, platform = architecture.split("/")

    # if we're deploying a custom image, we'll want to fetch info for the base image
    # for the purpose of booting the ephemeral OS installer
    if osystem == "custom" and distro_series:
        boot_resource = BootResource.objects.get_resource_for(
            osystem, arch, platform, distro_series
        )
        if boot_resource is not None:
            osystem, distro_series = boot_resource.split_base_image()

    # If we're not deploying Ubuntu we are just setting the kernel to be used
    # during deployment
    if osystem != "ubuntu":
        osystem = commissioning_osystem
        if osystem is undefined:
            osystem = Config.objects.get_config("commissioning_osystem")
        distro_series = commissioning_distro_series
        if distro_series is undefined:
            distro_series = Config.objects.get_config(
                "commissioning_distro_series"
            )

    os_release = osystem + "/" + distro_series
    kernel_str_valid = requested_kernel and validate_kernel_str(
        requested_kernel
    )
    min_compat_lvl_valid = min_compatibility_level and validate_kernel_str(
        min_compatibility_level
    )

    if kernel_str_valid:
        # Specific kernel was requested -- check whether it will work
        available_kernels = get_available_kernels_prioritising_platform(
            arch, os_release, platform
        )
        if requested_kernel not in available_kernels:
            raise ValidationError(
                "%s is not available for %s on %s."
                % (requested_kernel, os_release, architecture)
            )
        if not release_a_newer_than_b(requested_kernel, distro_series):
            raise ValidationError(
                f"{requested_kernel} is too old to use on {os_release}."
            )
        if min_compat_lvl_valid and (
            not release_a_newer_than_b(
                requested_kernel, min_compatibility_level
            )
        ):
            raise ValidationError(
                "chosen kernel (%s) is older than minimal kernel required by the machine (%s)."
                % (requested_kernel, min_compatibility_level)
            )
        return requested_kernel
    elif min_compat_lvl_valid:
        # No specific kernel was requested, but there is a minimal
        # compatibility level restriction. Look for kernels that could
        # fit the description.

        # Determine what kflavor is being used by check against a list of
        # known kflavors.
        valid_kflavors = {
            br.kflavor for br in BootResource.objects.exclude(kflavor=None)
        }
        _, _, _, kflavor = parse_subarch_kernel_string(min_compatibility_level)
        if not kflavor or kflavor not in valid_kflavors:
            kflavor = "generic"

        usable_kernels = get_available_kernels_prioritising_platform(
            arch, os_release, platform, kflavor=kflavor
        )
        for i in usable_kernels:
            if release_a_newer_than_b(
                i, min_compatibility_level
            ) and release_a_newer_than_b(i, distro_series):
                return i
        raise ValidationError(
            "%s has no kernels available which meet min_hwe_kernel(%s)."
            % (distro_series, min_compatibility_level)
        )

    # No specific kernel, no requirements. Pick the first kernel suitable
    # for the distro.
    available_kernels = get_available_kernels_prioritising_platform(
        arch, os_release, platform
    )
    for kernel in available_kernels:
        # TODO We need to switch to dataclasses to describe kernels.
        p = parse_subarch_kernel_string(kernel)
        old_style_platform = (
            not p.channel and p.platform and p.platform != "generic"
        )
        if old_style_platform and (
            kernel == requested_kernel or kernel == platform
        ):
            # We can do that because we filtered for `os_release` above
            return kernel
        elif release_a_newer_than_b(kernel, distro_series):
            return kernel
    raise ValidationError("%s has no kernels available." % distro_series)


def get_available_kernels_prioritising_platform(
    arch: str, os_release: str, platform: str, kflavor: str = None
) -> List[str]:
    """Wrapper around `get_kernels` that prioritises platform-exact
    kernels over platform-generic and generic kernels

    This way we may have both "platform-exact" and "platform-generic"
    kernels (e.g. `linux-raspi` generic and `linux-raspi-zero` exact)
    in a way that allows MAAS to choose the best platform-supporting
    kernel that is available to it.
    """

    # We cannot always use the generic kernels, because some platforms
    # won't boot with them. However, we still need to fetch them because
    # we want them at the end of the kernel list.
    generic_kernels = BootResource.objects.get_kernels(
        os_release,
        architecture=arch,
        platform="generic",
        kflavor=kflavor,
    )

    # Save DB queries for the vast majority of the machines
    if platform == "generic":
        return generic_kernels

    # Kernels are sorted by the rules of `get_release_version_from_string`,
    # meaning that platform-optimised kernels will end up being the last
    # on the list. While in other contexts this is reasonable, here we
    # want them to have priority over the generic ones. The idea is
    # simple: we fetch the kernels that match the platform exactly,
    # then we fetch the ones that *support* the platform,
    # "platform-generic" ones. The latter might also contain some
    # simply-generic kernels that we want to end up the last, so we
    # filter them out by using the simply-generic kernel list we fetch
    # earlier.
    #
    # TODO This part adds 6 extra queries and we might want to fix it
    platform_exact_kernels = BootResource.objects.get_kernels(
        os_release,
        architecture=arch,
        platform=platform,
        kflavor=kflavor,
        strict_platform_match=True,
    )
    platform_generic_kernels = BootResource.objects.get_kernels(
        os_release,
        architecture=arch,
        platform=platform,
        kflavor=kflavor,
        strict_platform_match=False,
    )

    # Generic kernel filtering, see above
    platform_kernels = list(platform_exact_kernels)
    generic_supporting_kernels = []
    for k in platform_generic_kernels:
        if k in generic_kernels:
            generic_supporting_kernels.append(k)
        else:
            platform_kernels.append(k)

    # Make [*platform-exact, *platform-generic, *generic]
    available_kernels = platform_kernels + generic_supporting_kernels
    return available_kernels


def validate_min_hwe_kernel(min_hwe_kernel):
    """Check that the min_hwe_kernel is avalible."""
    if not min_hwe_kernel or min_hwe_kernel == "":
        return ""
    compatibility_levels = (
        BootResource.objects.get_supported_kernel_compatibility_levels()
    )
    if min_hwe_kernel not in compatibility_levels:
        raise ValidationError(
            'No kernel matches ">=%s" requirement.' % min_hwe_kernel
        )
    else:
        return min_hwe_kernel
