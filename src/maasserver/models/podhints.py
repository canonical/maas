# Copyright 2016-2020 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model that holds hint information for a Pod."""

from django.db.models import (
    BigIntegerField,
    CASCADE,
    ForeignKey,
    IntegerField,
    ManyToManyField,
    Model,
    OneToOneField,
    SET_NULL,
)

from maasserver.models.cleansave import CleanSave
from maasserver.models.vmcluster import VMCluster


class PodHints(CleanSave, Model):
    """Hint information for a pod."""

    pod = OneToOneField("BMC", related_name="hints", on_delete=CASCADE)

    nodes = ManyToManyField("Node")

    cores = IntegerField(default=0)

    memory = IntegerField(default=0)

    cpu_speed = IntegerField(default=0)  # MHz

    local_storage = BigIntegerField(  # Bytes
        blank=False, null=False, default=0
    )

    cluster = ForeignKey(VMCluster, blank=True, null=True, on_delete=SET_NULL)
