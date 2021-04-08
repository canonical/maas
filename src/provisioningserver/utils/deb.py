# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities related to Debian packages."""


import dataclasses
from typing import Optional

from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("deb")

MAAS_PACKAGES = ("maas-region-api", "maas-rack-controller")


@dataclasses.dataclass
class DebVersion:
    """Information about a .deb version."""

    version: str


@dataclasses.dataclass
class DebVersionsInfo:
    """Information about .deb versions."""

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
        import apt_pkg

        apt_pkg.init()

    try:
        cache = apt_pkg.Cache(None)
        depcache = apt_pkg.DepCache(cache)
    except SystemError:
        maaslog.error(
            "Installed version could not be determined. Ensure "
            "/var/lib/dpkg/status is valid."
        )
        return None

    current, update = None, None
    for package in MAAS_PACKAGES:
        current, update = _get_deb_current_and_update(cache, depcache, package)
        if current:
            break
    else:
        return None
    return DebVersionsInfo(
        current=DebVersion(version=current),
        update=DebVersion(version=update) if update else None,
    )


def _get_deb_current_and_update(cache, depcache, package_name):
    try:
        package = cache[package_name]
    except KeyError:
        return None, None

    if package.current_ver is None:
        return None, None

    candidate = depcache.get_candidate_ver(package)
    return (
        package.current_ver.ver_str,
        candidate.ver_str if candidate else None,
    )
