# Copyright 2012-2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node user-data for cloud-init's use."""

from django.db.models import CASCADE, Manager, Model, OneToOneField

from maasserver.models.cleansave import CleanSave
from metadataserver.fields import Bin, BinaryField


class NodeUserDataManager(Manager):
    """Utility for the collection of NodeUserData items."""

    def set_user_data(self, node, data):
        """Set user data for the given node.

        If `data` is None, remove user data for the node.
        """
        if data is None:
            self._remove(node)
        else:
            self._set(node, data)

    def get_user_data(self, node):
        """Retrieve user data for the given node."""
        return self.get(node=node).data

    def has_user_data(self, node):
        """Do we have user data registered for node?"""
        return self.filter(node=node).exists()

    def _set(self, node, data):
        """Set actual user data for a node.  Not usable if data is None."""
        wrapped_data = Bin(data)
        (existing_entry, created) = self.get_or_create(
            node=node, defaults={"data": wrapped_data}
        )
        if not created:
            existing_entry.data = wrapped_data
            existing_entry.save()

    def _remove(self, node):
        """Remove metadata from node, if it has any any."""
        self.filter(node=node).delete()

    def bulk_set_user_data(self, nodes, data):
        """Set the user data for the given nodes in bulk.

        This is more efficient than calling `set_user_data` on each node.
        """
        self.filter(node__in=nodes).delete()
        if data is not None:
            self.bulk_create(
                self.model(node=node, data=Bin(data)) for node in nodes
            )


class NodeUserData(CleanSave, Model):
    """User-data portion of a node's metadata.

    When cloud-init sets up a node, it retrieves specific data for that node
    from the metadata service.  One portion of that is the "user-data" binary
    blob.

    :ivar node: Node that this is for.
    :ivar data: base64-encoded data.
    """

    objects = NodeUserDataManager()

    node = OneToOneField(
        "maasserver.Node", null=False, editable=False, on_delete=CASCADE
    )
    data = BinaryField(null=False)
