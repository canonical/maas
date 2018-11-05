# Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `CacheSet`."""

from maasserver.api.support import OperationsHandler
from maasserver.audit import create_audit_event
from maasserver.enum import (
    ENDPOINT,
    NODE_STATUS,
)
from maasserver.exceptions import (
    MAASAPIBadRequest,
    MAASAPIValidationError,
    NodeStateViolation,
)
from maasserver.forms import (
    CreateCacheSetForm,
    UpdateCacheSetForm,
)
from maasserver.models import (
    CacheSet,
    Machine,
)
from maasserver.permissions import NodePermission
from piston3.utils import rc
from provisioningserver.events import EVENT_TYPES


DISPLAYED_CACHE_SET_FIELDS = (
    'system_id',
    'id',
    'name',
    'cache_device',
)


class BcacheCacheSetsHandler(OperationsHandler):
    """Manage bcache cache sets on a machine."""
    api_doc_section_name = "Bcache Cache Sets"
    update = delete = None
    fields = DISPLAYED_CACHE_SET_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('bcache_cache_sets_handler', ["system_id"])

    def read(self, request, system_id):
        """List all bcache cache sets belonging to a machine.

        Returns 404 if the machine is not found.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.view)
        return CacheSet.objects.get_cache_sets_for_node(machine)

    def create(self, request, system_id):
        """Creates a bcache Cache Set.

        :param cache_device: Cache block device.
        :param cache_partition: Cache partition.

        Specifying both a cache_device and a cache_partition is not allowed.

        Returns 404 if the machine is not found.
        Returns 409 if the machine is not Ready.
        """
        machine = Machine.objects.get_node_or_404(
            system_id, request.user, NodePermission.admin)
        if machine.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create cache set because the node is not Ready.")
        form = CreateCacheSetForm(machine, data=request.data)
        if form.is_valid():
            create_audit_event(
                EVENT_TYPES.NODE, ENDPOINT.API, request,
                system_id, "Created bcache cache set.")
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class BcacheCacheSetHandler(OperationsHandler):
    """Manage bcache cache set on a machine."""
    api_doc_section_name = "Bcache Cache Set"
    create = None
    model = CacheSet
    fields = DISPLAYED_CACHE_SET_FIELDS

    @classmethod
    def resource_uri(cls, cache_set=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        cache_set_id = "id"
        if cache_set is not None:
            cache_set_id = cache_set.id
            node = cache_set.get_node()
            if node is not None:
                system_id = node.system_id
        return ('bcache_cache_set_handler', (system_id, cache_set_id))

    @classmethod
    def system_id(cls, cache_set):
        node = cache_set.get_node()
        return None if node is None else node.system_id

    @classmethod
    def cache_device(cls, cache_set):
        """Return the cache device for this cache set."""
        return cache_set.get_device()

    def read(self, request, system_id, id):
        """Read bcache cache set on a machine.

        Returns 404 if the machine or cache set is not found.
        """
        return CacheSet.objects.get_cache_set_or_404(
            system_id, id, request.user, NodePermission.view)

    def delete(self, request, system_id, id):
        """Delete bcache cache set on a machine.

        Returns 400 if the cache set is in use.
        Returns 404 if the machine or cache set is not found.
        Returns 409 if the machine is not Ready.
        """
        cache_set = CacheSet.objects.get_cache_set_or_404(
            system_id, id, request.user, NodePermission.admin)
        node = cache_set.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete cache set because the machine is not Ready.")
        if cache_set.filesystemgroup_set.exists():
            raise MAASAPIBadRequest(
                "Cannot delete cache set; it's currently in use.")
        else:
            cache_set.delete()
            create_audit_event(
                EVENT_TYPES.NODE, ENDPOINT.API, request,
                system_id, "Deleted bcache cache set.")
            return rc.DELETED

    def update(self, request, system_id, id):
        """Update bcache cache set on a machine.

        :param cache_device: Cache block device to replace current one.
        :param cache_partition: Cache partition to replace current one.

        Specifying both a cache_device and a cache_partition is not allowed.

        Returns 404 if the machine or the cache set is not found.
        Returns 409 if the machine is not Ready.
        """
        cache_set = CacheSet.objects.get_cache_set_or_404(
            system_id, id, request.user, NodePermission.admin)
        node = cache_set.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update cache set because the machine is not Ready.")
        form = UpdateCacheSetForm(cache_set, data=request.data)
        if form.is_valid():
            create_audit_event(
                EVENT_TYPES.NODE, ENDPOINT.API, request,
                system_id, "Updated bcache cache set.")
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
