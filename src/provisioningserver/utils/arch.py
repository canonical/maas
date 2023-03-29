# Copyright 2021 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Helper for handling architectures."""

from functools import lru_cache
import os

# Architectures as defined by:
# https://github.com/lxc/lxd/blob/master/shared/osarch/architectures.go
# https://www.debian.org/releases/bullseye/amd64/ch02s01.en.html
DEBIAN_TO_KERNEL_ARCHITECTURES = {
    "i386": "i686",
    "amd64": "x86_64",
    "arm64": "aarch64",
    "ppc64el": "ppc64le",
    "s390x": "s390x",
    "mips": "mips",
    "mips64el": "mips64",
}
KERNEL_TO_DEBIAN_ARCHITECTURES = {
    v: k for k, v in DEBIAN_TO_KERNEL_ARCHITECTURES.items()
}


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


def kernel_to_debian_architecture(kernel_arch):
    """Map a kernel architecture to Debian architecture."""
    return f"{KERNEL_TO_DEBIAN_ARCHITECTURES[kernel_arch]}/generic"


def debian_to_kernel_architecture(debian_arch):
    """Map a Debian architecture to kernel architecture."""
    return DEBIAN_TO_KERNEL_ARCHITECTURES[debian_arch.removesuffix("/generic")]
