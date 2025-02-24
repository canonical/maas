# Copyright 2014-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helpers for operating systems in testing."""

from random import randint

from maascommon.osystem import CustomOS, OperatingSystemRegistry
from maasserver.enum import BOOT_RESOURCE_TYPE
from maasserver.models import Node
from maasserver.testing.factory import factory


def make_osystem_with_releases(
    testcase,
    osystem_name: str | None = None,
    releases: list[str] | None = None,
    aliases: list[str] | None = None,
    rtype: BOOT_RESOURCE_TYPE = BOOT_RESOURCE_TYPE.UPLOADED,
) -> tuple[str, list[str]]:
    """Generate an arbitrary operating system.

    :param osystem_name: The operating system name. Useful in cases where
        we need to test that not supplying an os works correctly.
    :param releases: The list of releases name. Useful in cases where
        we need to test that not supplying a release works correctly.
    :param aliases: The list of aliases name. If supplied, it must be
        a 1 to 1 match with the releases list.
    :param rtype: The rtype of the BootResource.
    """
    if osystem_name is None:
        osystem_name = factory.make_name("os")
    if releases is None:
        releases = [factory.make_name("release") for _ in range(3)]
    if aliases is None:
        aliases = [factory.make_name("alias") for _ in range(len(releases))]
    if osystem_name not in OperatingSystemRegistry:
        OperatingSystemRegistry.register_item(osystem_name, CustomOS())
        testcase.addCleanup(
            OperatingSystemRegistry.unregister_item, osystem_name
        )
    # Make sure the commissioning Ubuntu release and all created releases
    # are available to all architectures.
    architectures = [
        node.architecture for node in Node.objects.distinct("architecture")
    ]
    if len(architectures) == 0:
        architectures.append("%s/generic" % factory.make_name("arch"))
    for arch in architectures:
        factory.make_default_ubuntu_release_bootable(arch.split("/")[0])
        for idx in range(len(releases)):
            factory.make_BootResource(
                rtype=rtype,
                name=(f"{osystem_name}/{releases[idx]}"),
                alias=(f"{osystem_name}/{aliases[idx]}"),
                architecture=arch,
            )
    return osystem_name, releases


def patch_usable_osystems(
    testcase, osystems=None, allow_empty: bool = True
) -> None:
    """Set a fixed list of usable operating systems.

    A usable operating system is one for which boot images are available.

    :param testcase: A `TestCase` whose `patch` this function can use.
    :param osystems: Optional list of operating systems.  If omitted,
        defaults to a list (which may be empty) of random operating systems.
    """
    start = 0
    if allow_empty is False:
        start = 1
    if osystems is None:
        osystems = [
            make_osystem_with_releases(testcase)
            for _ in range(randint(start, 2))
        ]
    # Make sure the Commissioning release is always available.
    factory.make_default_ubuntu_release_bootable()


def make_usable_osystem(
    testcase,
    osystem_name: str | None = None,
    releases: list[str] | None = None,
    aliases: list[str] | None = None,
    rtype: BOOT_RESOURCE_TYPE = BOOT_RESOURCE_TYPE.UPLOADED,
):
    """Return arbitrary operating system, and make it "usable."

    :param testcase: A `TestCase` whose `patch` this function can pass to
        `patch_usable_osystems`.
    :param osystem_name: The operating system name. Useful in cases where
        we need to test that not supplying an os works correctly.
    :param releases: The list of releases name. Useful in cases where
        we need to test that not supplying a release works correctly.
    :param aliases: The list of aliases name. If supplied, it must be
        a 1 to 1 match with the releases list.
    :param rtype: The rtype of the BootResource.
    """
    osystem = make_osystem_with_releases(
        testcase,
        osystem_name=osystem_name,
        releases=releases,
        aliases=aliases,
        rtype=rtype,
    )
    patch_usable_osystems(testcase, [osystem])
    return osystem
