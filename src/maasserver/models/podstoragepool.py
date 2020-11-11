# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Storage pool for a Pod."""


from django.db.models import (
    BigIntegerField,
    CASCADE,
    CharField,
    ForeignKey,
    Model,
    Sum,
)

from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave


class PodStoragePool(CleanSave, Model):
    """Storage pool for a pod."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    pod = ForeignKey(
        "BMC",
        blank=False,
        null=False,
        related_name="storage_pools",
        on_delete=CASCADE,
    )

    name = CharField(max_length=255, null=False, blank=False)

    pool_id = CharField(max_length=255, null=False, blank=False)

    pool_type = CharField(max_length=255, null=False, blank=False)

    path = CharField(max_length=4095, null=False, blank=False)

    storage = BigIntegerField(blank=False, null=False, default=0)  # Bytes

    def get_used_storage(self):
        """Calculate the used storage for this pod."""
        # Circular import.
        from maasserver.models.physicalblockdevice import PhysicalBlockDevice

        query = PhysicalBlockDevice.objects.filter(storage_pool=self)
        query = query.aggregate(size=Sum("size"))
        size = query["size"]
        if size is None:
            size = 0
        return size
