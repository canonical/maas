# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""API handlers: `CacheSet`."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type

from maasserver.api.support import OperationsHandler
from maasserver.enum import (
    NODE_PERMISSION,
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
    Node,
)
from piston.utils import rc


DISPLAYED_CACHE_SET_FIELDS = (
    'id',
    'name',
    'cache_device',
)


class BcacheCacheSetsHandler(OperationsHandler):
    """Manage bcache cache sets on a node."""
    api_doc_section_name = "Bcache Cache Sets"
    update = delete = None
    fields = DISPLAYED_CACHE_SET_FIELDS

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        # See the comment in NodeHandler.resource_uri.
        return ('bcache_cache_sets_handler', ["system_id"])

    def read(self, request, system_id):
        """List all bcache cache sets belonging to node.

        Returns 404 if the node is not found.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.VIEW)
        return CacheSet.objects.get_cache_sets_for_node(node)

    def create(self, request, system_id):
        """Creates a Bcache Cache Set.

        :param cache_device: Cache block device.
        :param cache_partition: Cache partition.

        Specifying both a cache_device and a cache_partition is not allowed.

        Returns 404 if the node is not found.
        Returns 409 if the node is not Ready.
        """
        node = Node.nodes.get_node_or_404(
            system_id, request.user, NODE_PERMISSION.ADMIN)
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot create cache set because the node is not Ready.")
        form = CreateCacheSetForm(node, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)


class BcacheCacheSetHandler(OperationsHandler):
    """Manage bcache cache set on a node."""
    api_doc_section_name = "Bcache Cache Set"
    create = None
    model = CacheSet
    fields = DISPLAYED_CACHE_SET_FIELDS

    @classmethod
    def resource_uri(cls, cache_set=None):
        # See the comment in NodeHandler.resource_uri.
        system_id = "system_id"
        cache_set_id = "cache_set_id"
        if cache_set is not None:
            cache_set_id = cache_set.id
            node = cache_set.get_node()
            if node is not None:
                system_id = node.system_id
        return ('bcache_cache_set_handler', (system_id, cache_set_id))

    @classmethod
    def cache_device(cls, cache_set):
        """Return the cache device for this cache set."""
        return cache_set.get_device()

    def read(self, request, system_id, cache_set_id):
        """Read bcache cache set on node.

        Returns 404 if the node or cache set is not found.
        """
        return CacheSet.objects.get_cache_set_or_404(
            system_id, cache_set_id, request.user, NODE_PERMISSION.VIEW)

    def delete(self, request, system_id, cache_set_id):
        """Delete cache set on node.

        Returns 400 if the cache set is in use.
        Returns 404 if the node or cache set is not found.
        Returns 409 if the node is not Ready.
        """
        cache_set = CacheSet.objects.get_cache_set_or_404(
            system_id, cache_set_id, request.user, NODE_PERMISSION.ADMIN)
        node = cache_set.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot delete cache set because the node is not Ready.")
        if cache_set.filesystemgroup_set.exists():
            raise MAASAPIBadRequest(
                "Cannot delete cache set; it's currently in use.")
        else:
            cache_set.delete()
            return rc.DELETED

    def update(self, request, system_id, cache_set_id):
        """Delete bcache on node.

        :param cache_device: Cache block device to replace current one.
        :param cache_partition: Cache partition to replace current one.

        Specifying both a cache_device and a cache_partition is not allowed.

        Returns 404 if the node or the cache set is not found.
        Returns 409 if the node is not Ready.
        """
        cache_set = CacheSet.objects.get_cache_set_or_404(
            system_id, cache_set_id, request.user, NODE_PERMISSION.ADMIN)
        node = cache_set.get_node()
        if node.status != NODE_STATUS.READY:
            raise NodeStateViolation(
                "Cannot update cache set because the node is not Ready.")
        form = UpdateCacheSetForm(cache_set, data=request.data)
        if form.is_valid():
            return form.save()
        else:
            raise MAASAPIValidationError(form.errors)
