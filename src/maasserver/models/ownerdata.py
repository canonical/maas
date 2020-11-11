# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Owner key/value data placed on a machine while it is owned."""


from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    Model,
    TextField,
)

from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave


class OwnerDataManager(Manager):
    def set_owner_data(self, node, owner_data):
        """Set the `owner_data` on `node`.

        This will update any keys for `node` in `owner_data`. If the key has
        the value of None then that key will be removed from the `node`.
        """
        # Remove the keys set to None value.
        keys_to_remove = {
            key for key, value in owner_data.items() if value is None
        }
        if len(keys_to_remove) > 0:
            self.filter(node=node, key__in=keys_to_remove).delete()

        # Create/update the owner data.
        for key, value in owner_data.items():
            if value is not None:
                data, created = self.get_or_create(
                    node=node, key=key, defaults={"value": value}
                )
                if not created and data.value != value:
                    data.value = value
                    data.save()


class OwnerData(CleanSave, Model):
    """Owner key/value data placed on a machine while it is owned."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

        unique_together = ("node", "key")

    objects = OwnerDataManager()

    node = ForeignKey("Node", blank=False, null=False, on_delete=CASCADE)

    key = CharField(max_length=255, blank=False, null=False)

    value = TextField(blank=False, null=False)
