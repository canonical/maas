# Copyright 2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from django.db.models import (
    BooleanField,
    CASCADE,
    ForeignKey,
    IntegerField,
    OneToOneField,
    SET_NULL,
    TextField,
)

from maasserver.models.bmc import BMC
from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Machine
from maasserver.models.timestampedmodel import TimestampedModel


class VirtualMachine(CleanSave, TimestampedModel):
    """A virtual machine managed by a VM host."""

    identifier = TextField()
    pinned_cores = ArrayField(IntegerField(), blank=True, default=list)
    unpinned_cores = IntegerField(default=0, blank=True)
    memory = IntegerField(default=0)
    hugepages_backed = BooleanField(default=False)
    machine = OneToOneField(
        Machine,
        SET_NULL,
        default=None,
        blank=True,
        null=True,
        editable=False,
        related_name="virtualmachine",
    )
    bmc = ForeignKey(BMC, editable=False, on_delete=CASCADE)

    class Meta:
        unique_together = [("bmc", "identifier")]

    def clean(self):
        super().clean()
        if self.pinned_cores and self.unpinned_cores:
            raise ValidationError(
                "VirtualMachine can't have both pinned and unpinned cores"
            )
