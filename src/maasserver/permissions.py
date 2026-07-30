# Copyright 2018-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Permission enumerations."""

import enum


class NodePermission(enum.Enum):
    """Permissions relating to nodes."""

    view = "view"
    edit = "edit"
    lock = "lock"
    admin = "admin"
    admin_read = "admin_read"


class ResourcePoolPermission(enum.Enum):
    """Permissions for `ResourcePool`."""

    view = "view"
    edit = "edit"
    create = "create"
    delete = "delete"
