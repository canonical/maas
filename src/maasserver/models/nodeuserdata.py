# Copyright 2012-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Node user-data for cloud-init's use."""

from django.db.models import CASCADE, ForeignKey, Manager, Model
from django.db.models.fields import BooleanField

from maasserver.models.cleansave import CleanSave
from metadataserver.fields import Bin, BinaryField


class NodeUserDataManager(Manager):
    """Utility for the collection of NodeUserData items."""

    def set_user_data_for_ephemeral_env(self, node, data):
        """Set user data for the given node.

        If `data` is None, remove user data for the node.
        """
        if data is None:
            self._remove(node, for_ephemeral_environment=True)
        else:
            self._set(node, data, for_ephemeral_environment=True)

    def get_user_data_for_ephemeral_env(self, node):
        """Retrieve user data for the given node."""
        return self.get(node=node, for_ephemeral_environment=True).data

    def has_any_user_data(self, node):
        """Do we have user data registered for node?"""
        return self.filter(node=node).exists()

    def set_user_data_for_user_env(self, node, data):
        """Set user data for the given node.

        If `data` is None, remove user data for the node.
        """
        if data is None:
            self._remove(node, for_ephemeral_environment=False)
        else:
            self._set(node, data, for_ephemeral_environment=False)

    def get_user_data_for_user_env(self, node):
        """Retrieve user data for the given node."""
        return self.get(node=node, for_ephemeral_environment=False).data

    def has_user_data_for_user_env(self, node):
        """Do we have user data registered for node?"""
        return self.filter(node=node, for_ephemeral_environment=False).exists()

    def _set(self, node, data, for_ephemeral_environment: bool):
        """Set actual user data for a node.  Not usable if data is None."""
        wrapped_data = Bin(data)
        (existing_entry, created) = self.get_or_create(
            node=node,
            for_ephemeral_environment=for_ephemeral_environment,
            defaults={"data": wrapped_data},
        )
        if not created:
            existing_entry.data = wrapped_data
            existing_entry.save()

    def _remove(self, node, for_ephemeral_environment: bool):
        """Remove metadata from node, if it has any any."""
        self.filter(
            node=node, for_ephemeral_environment=for_ephemeral_environment
        ).delete()


class NodeUserData(CleanSave, Model):
    """User-data portion of a node's metadata.

    When cloud-init sets up a node, it retrieves specific data for that node
    from the metadata service.  One portion of that is the "user-data" binary
    blob.

    :ivar node: Node that this is for.
    :ivar data: base64-encoded data.
    """

    class Meta:
        unique_together = ("node", "for_ephemeral_environment")

    objects = NodeUserDataManager()

    node = ForeignKey(
        "maasserver.Node", null=False, editable=False, on_delete=CASCADE
    )

    data = BinaryField(null=False)

    for_ephemeral_environment = BooleanField(null=False)
