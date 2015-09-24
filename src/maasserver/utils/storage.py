# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utilities for working with the storage model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "get_effective_filesystem"
]


def get_effective_filesystem(model):
    """Return the effective `Filesystem` for the `model`.

    A `BlockDevice` or `Partition` can have up to two `Filesystem` one with
    `acquired` set to False and another set to `True`. When the `Node` for
    `model` is in an allocated state the acquired `Filesystem` will be used
    over the non-acquired `Filesystem`.

    :param model: Model to get active `Filesystem` from.
    :type model: Either `BlockDevice` or `Partition`.
    :returns: Active `Filesystem` for `model`.
    :rtype: `Filesystem`
    """
    from maasserver.models import BlockDevice, Partition
    assert isinstance(model, (BlockDevice, Partition))

    node = model.get_node()
    filesystems = list(model.filesystem_set.all())
    if node.is_in_allocated_state():
        # Return the acquired filesystem.
        for filesystem in filesystems:
            if filesystem.acquired:
                return filesystem
        # No acquired filesystem, could be a filesystem that is not
        # mountable so we return that filesystem.
        for filesystem in filesystems:
            if not filesystem.is_mountable():
                return filesystem
        return None
    else:
        # Not in allocated state so return the filesystem that is not an
        # acquired filesystem.
        for filesystem in filesystems:
            if not filesystem.acquired:
                return filesystem
        return None
