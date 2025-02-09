# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to Debian packages."""

import dataclasses
from typing import Optional

from provisioningserver.enum import CONTROLLER_INSTALL_TYPE
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("deb")

MAAS_PACKAGES = ("maas-region-api", "maas-rack-controller")

APT_PKG = None


def get_apt_pkg():
    """Return the initalized apt_pkg."""
    global APT_PKG
    # Make sure that .init() is only called after initial import.
    # init() can be slow, and cause memory leaks if called multiple
    # times.
    if APT_PKG is None:
        import apt_pkg

        apt_pkg.init()
        APT_PKG = apt_pkg
    return APT_PKG


@dataclasses.dataclass
class DebVersion:
    """Information about a .deb version."""

    version: str
    origin: str = ""


@dataclasses.dataclass
class DebVersionsInfo:
    """Information about .deb versions."""

    install_type = CONTROLLER_INSTALL_TYPE.DEB

    current: DebVersion
    update: Optional[DebVersion] = None

    def __post_init__(self):
        # deserialize nested dataclasses, if needed
        if isinstance(self.current, dict):
            self.current = DebVersion(**self.current)
        if isinstance(self.update, dict):
            self.update = DebVersion(**self.update)


def get_deb_versions_info(apt_pkg=None) -> Optional[DebVersionsInfo]:
    """Return versions information for Debian-based MAAS."""

    if apt_pkg is None:
        apt_pkg = get_apt_pkg()

    try:
        cache = apt_pkg.Cache(None)
    except SystemError:
        maaslog.error(
            "Installed version could not be determined. Ensure "
            "/var/lib/dpkg/status is valid."
        )
        return None

    depcache = apt_pkg.DepCache(cache)
    sources = apt_pkg.SourceList()
    sources.read_main_list()
    policy = apt_pkg.Policy(cache)
    policy.init_defaults()

    (
        current,
        update,
    ) = (
        None,
        None,
    )
    for package in MAAS_PACKAGES:
        current, update = _get_deb_current_and_update(
            cache, depcache, sources, policy, package
        )
        if current:
            break
    else:
        return None
    return DebVersionsInfo(current=current, update=update)


def _get_deb_current_and_update(
    cache, depcache, sources, policy, package_name
):
    try:
        package = cache[package_name]
    except KeyError:
        return None, None

    current_ver = package.current_ver
    if current_ver is None:
        return None, None

    current = DebVersion(
        version=current_ver.ver_str,
        origin=_get_deb_origin(sources, policy, current_ver),
    )

    update = None
    candidate_ver = depcache.get_candidate_ver(package)
    if candidate_ver and candidate_ver != current_ver:
        update = DebVersion(
            version=candidate_ver.ver_str,
            origin=_get_deb_origin(sources, policy, candidate_ver),
        )
    return current, update


def _get_deb_origin(sources, policy, version):
    origins = []
    for package_file, _ in version.file_list:
        index = sources.find_index(package_file)
        if not index:
            continue
        origin = (
            f"{index.archive_uri('')} "
            f"{package_file.codename}/{package_file.component}"
        )
        origins.append((policy.get_priority(package_file), origin))

    if not origins:
        return ""
    # return the origin with the highest priority
    return sorted(origins, reverse=True)[0][1]
