# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

__all__ = [
    "StorageHandler",
    "StoragesHandler",
    ]

from maasserver.api.nodes import (
    NodeHandler,
    NodesHandler,
)
from maasserver.enum import NODE_PERMISSION
from maasserver.models.node import Storage
from piston3.utils import rc

# Storage fields exposed on the API.
DISPLAYED_STORAGE_FIELDS = (
    'system_id',
    'hostname',
    'storage_type',
    'node_type',
    'node_type_name',
    )


class StorageHandler(NodeHandler):
    """Manage an individual storage system.

    The storage is identified by its system_id.
    """
    api_doc_section_name = "Storage"

    create = update = None
    model = Storage
    fields = DISPLAYED_STORAGE_FIELDS

    @classmethod
    def storage_type(cls, storage):
        return storage.power_type

    def delete(self, request, system_id):
        """Delete a specific Storage.

        Returns 404 if the storage is not found.
        Returns 403 if the user does not have permission to delete the storage.
        Returns 204 if the storage is successfully deleted.
        """
        storage = self.model.objects.get_node_or_404(
            system_id=system_id, user=request.user,
            perm=NODE_PERMISSION.ADMIN)
        storage.delete()
        return rc.DELETED

    @classmethod
    def resource_uri(cls, storage=None):
        # This method is called by piston in two different contexts:
        # - when generating an uri template to be used in the documentation
        # (in this case, it is called with node=None).
        # - when populating the 'resource_uri' field of an object
        # returned by the API (in this case, node is a node object).
        storage_system_id = "system_id"
        if storage is not None:
            storage_system_id = storage.system_id
        return ('storage_handler', (storage_system_id,))


class StoragesHandler(NodesHandler):
    """Manage the collection of all the storage in the MAAS."""
    api_doc_section_name = "Storages"
    create = update = delete = None
    base_model = Storage

    @classmethod
    def resource_uri(cls, *args, **kwargs):
        return ('storages_handler', [])
