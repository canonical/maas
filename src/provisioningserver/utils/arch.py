# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper for handling architectures."""

from functools import lru_cache
import os


@lru_cache(maxsize=1)
def get_architecture():
    """Get the Debian architecture of the running system."""
    arch = os.getenv("SNAP_ARCH")
    if not arch:
        # assume it's a deb environment
        import apt_pkg

        apt_pkg.init()
        arch = apt_pkg.get_architectures()[0]
    return arch
