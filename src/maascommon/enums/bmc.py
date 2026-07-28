#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import IntEnum


class BmcType(IntEnum):
    """Valid BMC types.

    POD is retained only so that leftover rows from deployments that used
    KVM/VM host (Pod) support before its removal can still be read and
    migrated. New BMCs are never created with this type.
    """

    DEFAULT = 0
    BMC = 0
    POD = 1
