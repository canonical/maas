#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class RdnsMode(IntEnum):
    """The vocabulary of a `Subnet`'s possible reverse DNS modes."""

    # By default, we do what we've always done: assume we rule the DNS world.
    DEFAULT = 2
    # Do not generate reverse DNS for this Subnet.
    DISABLED = 0
    # Generate reverse DNS only for the CIDR.
    ENABLED = 1
    # Generate RFC2317 glue if needed (Subnet is too small for its own zone.)
    RFC2317 = 2
