# Copyright 2022-2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

from maasserver.authorization import (
    can_edit_global_entities,
    can_edit_machines,
)
from maasserver.enum import NODE_TYPE
from maasserver.models.blockdevice import BlockDevice
from maasserver.models.discovery import Discovery
from maasserver.models.dnsdata import DNSData
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import Domain
from maasserver.models.fabric import Fabric
from maasserver.models.filesystemgroup import FilesystemGroup
from maasserver.models.interface import Interface
from maasserver.models.iprange import IPRange
from maasserver.models.node import Node
from maasserver.models.reservedip import ReservedIP
from maasserver.models.resourcepool import ResourcePool
from maasserver.models.space import Space
from maasserver.models.staticroute import StaticRoute
from maasserver.models.subnet import Subnet
from maasserver.models.tag import Tag
from maasserver.models.vlan import VLAN
from maasserver.openfga import get_openfga_client
from maasserver.permissions import NodePermission, ResourcePoolPermission
from provisioningserver.utils import is_instance_or_subclass

# Some actions are applied to model object types global to MAAS; not
# necessarily a particular object. The following objects cannot be created or
# changed by non-administrative users, but superusers can always create, read
# write, or delete them.
UNRESTRICTED_READ_MODELS = (
    DNSData,
    DNSResource,
    Domain,
    Fabric,
    IPRange,
    ReservedIP,
    ResourcePool,
    Space,
    Subnet,
    Tag,
    StaticRoute,
    VLAN,
)

# The following model objects are restricted from non-administrative users.
# They cannot be seen (or created, or modified, or deleted) by "normal" users.
ADMIN_RESTRICTED_MODELS = (Discovery,)

# ADMIN_PERMISSIONS applies to the model objects in ADMIN_RESTRICTED_MODELS.
# These model objects are restricted to administrators only; permission checks
# will return True for administrators given any of the following permissions:
ADMIN_PERMISSIONS = (
    NodePermission.view,
    NodePermission.edit,
    NodePermission.admin,
    NodePermission.admin_read,
)


class MAASAuthorizationBackend(ModelBackend):
    supports_object_permissions = True

    def authenticate(self, request, username=None, **kwargs):
        authenticated = super().authenticate(
            request, username=username, **kwargs
        )
        if authenticated:
            user = User.objects.get(username=username)
            if not user.userprofile.is_local:
                return
        return authenticated

    def has_perm(self, user, perm, obj=None):
        self._sanity_checks(perm, obj=obj)
        if not user.is_active:
            return False

        if perm == NodePermission.admin and obj is None:
            return can_edit_machines(user)

        elif perm == NodePermission.view and obj is None:
            return True

        if isinstance(perm, ResourcePoolPermission):
            return self._perm_resource_pool(user, perm, obj)

        if isinstance(obj, (Node, BlockDevice, FilesystemGroup)):
            if isinstance(obj, (BlockDevice, FilesystemGroup)):
                obj = obj.get_node()
            if perm == NodePermission.view:
                return self._can_view(user, obj)
            elif perm == NodePermission.edit:
                return not obj.locked and self._can_edit(user, obj)
            elif perm == NodePermission.lock:
                return obj.pool_id is not None and self._can_edit(user, obj)
            elif perm == NodePermission.admin_read:
                return self._can_admin(user, obj)
            elif perm == NodePermission.admin:
                return not obj.locked and self._can_admin(user, obj)
            else:
                raise NotImplementedError(
                    "Invalid permission check (invalid permission name: %s)."
                    % perm
                )
        elif isinstance(obj, Interface):
            node = obj.get_node()
            if node is None:
                return can_edit_machines(user)
            if perm == NodePermission.view:
                return self._can_view(user, node)
            elif perm == NodePermission.edit:
                if node.node_type == NODE_TYPE.MACHINE:
                    return self._can_admin(user, node)
                return self._can_edit(user, node)
            elif perm == NodePermission.admin:
                return self._can_admin(user, node)
            else:
                raise NotImplementedError(
                    "Invalid permission check (invalid permission name: %s)."
                    % perm
                )
        elif is_instance_or_subclass(obj, UNRESTRICTED_READ_MODELS):
            if perm == NodePermission.view:
                return get_openfga_client().can_view_global_entities(user)
            elif perm in ADMIN_PERMISSIONS:
                return can_edit_global_entities(user)
            else:
                raise NotImplementedError(
                    "Invalid permission check (invalid permission name: %s)."
                    % perm
                )
        elif is_instance_or_subclass(obj, ADMIN_RESTRICTED_MODELS):
            if perm in ADMIN_PERMISSIONS:
                return can_edit_global_entities(user)
            else:
                raise NotImplementedError(
                    "Invalid permission check (invalid permission name: %s)."
                    % perm
                )
        else:
            raise NotImplementedError(
                "Invalid permission check (invalid object type)."
            )

    def _sanity_checks(self, perm, obj=None):
        if (
            obj is not None
            and isinstance(obj, ResourcePool)
            and not isinstance(perm, ResourcePoolPermission)
        ):
            raise TypeError(
                "obj type of ResourcePool must be checked "
                "against a `ResourcePoolPermission`."
            )

    def _can_view(self, user, machine):
        if machine.pool_id is None:
            return True
        return (
            machine.owner_id is None
            or machine.owner_id == user.id
            or get_openfga_client().can_view_machines_in_pool(
                user, machine.pool_id
            )
        )

    def _can_edit(self, user, machine):
        editable = machine.owner_id is None or machine.owner_id == user.id
        return editable or get_openfga_client().can_edit_machines_in_pool(
            user, machine.pool_id
        )

    def _can_admin(self, user, machine):
        if machine.pool_id is None:
            return get_openfga_client().can_edit_machines(user)
        return get_openfga_client().can_edit_machines_in_pool(
            user, machine.pool_id
        )

    def _perm_resource_pool(self, user, perm, obj=None):
        if (
            perm == ResourcePoolPermission.create
            or perm == ResourcePoolPermission.delete
        ):
            return get_openfga_client().can_edit_machines(user)

        if not isinstance(obj, ResourcePool):
            raise ValueError(
                "only `ResourcePoolPermission.(create|delete)` can be used "
                "without an `obj`."
            )

        if perm == ResourcePoolPermission.edit:
            return get_openfga_client().can_edit_machines_in_pool(user, obj.id)
        elif perm == ResourcePoolPermission.view:
            return get_openfga_client().can_view_available_machines_in_pool(
                user, obj.id
            )

        raise ValueError("unknown ResourcePoolPermission value: %s" % perm)
