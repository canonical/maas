
# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Permission enumerations."""

__all__ = [
    'NodePermission',
    ]

import enum


class NodePermission(enum.Enum):
    """Permissions relating to nodes."""

    view = 'view'
    edit = 'edit'
    lock = 'lock'
    admin = 'admin'
