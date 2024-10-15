#  Copyright 2024 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

from enum import Enum


class RbacResourceType(str, Enum):
    MAAS = "maas"
    RESOURCE_POOL = "resource-pool"

    def __str__(self):
        return str(self.value)


class RbacPermission(str, Enum):
    VIEW = "view"
    VIEW_ALL = "view-all"
    DEPLOY_MACHINES = "deploy-machines"
    ADMIN_MACHINES = "admin-machines"
    EDIT = "edit"
    MAAS_ADMIN = "admin"

    def __str__(self):
        return str(self.value)
