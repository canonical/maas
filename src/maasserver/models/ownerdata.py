# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Owner key/value data placed on a machine while it is owned."""

import re

from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    Model,
    TextField,
)

from maasserver.models.cleansave import CleanSave

DATA_KEY_RE = re.compile(r"[\w.-]+$")


class OwnerDataManager(Manager):
    def set_owner_data(self, node, owner_data):
        """Set the `owner_data` on `node`.

        This will update any keys for `node` in `owner_data`. If the key has
        the value of None then that key will be removed from the `node`.
        """
        to_remove = set()
        for key, value in owner_data.items():
            if value is None:
                to_remove.add(key)
            else:
                if not DATA_KEY_RE.match(key):
                    raise ValueError("Invalid character in key name")

                self.update_or_create(
                    node=node, key=key, defaults={"value": value}
                )
        if to_remove:
            self.delete_owner_data(node, to_remove)

    def get_owner_data(self, node):
        # Note: ownerdata_set is prefetched, so this is more efficient than it
        #       otherwise appears. See NODES_PREFETCH in maasserver.api.nodes.
        return {data.key: data.value for data in node.ownerdata_set.all()}

    def delete_owner_data(self, node, keys):
        node.ownerdata_set.filter(key__in=keys).delete()


class OwnerData(CleanSave, Model):
    """Owner key/value data placed on a machine while it is owned."""

    class Meta:
        unique_together = ("node", "key")

    objects = OwnerDataManager()

    node = ForeignKey("Node", blank=False, null=False, on_delete=CASCADE)

    key = CharField(max_length=255, blank=False, null=False)

    value = TextField(blank=False, null=False)
