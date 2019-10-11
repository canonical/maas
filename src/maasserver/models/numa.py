__all__ = ["create_default_numanode"]


from datetime import datetime

from django.contrib.postgres.fields import ArrayField
from django.db.models import CASCADE, ForeignKey, IntegerField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class NUMANode(CleanSave, TimestampedModel):
    """A NUMA node in a Node."""

    node = ForeignKey("Node", null=False, editable=False, on_delete=CASCADE)
    index = IntegerField(default=0)
    memory = IntegerField()
    cores = ArrayField(IntegerField(), blank=True)

    class Meta:
        unique_together = [("node", "index")]


def create_default_numanode(machine):
    """Create the default "0" NUMA node for a machine."""
    now = datetime.utcnow()
    return NUMANode.objects.create(
        created=now,
        updated=now,
        node=machine,
        memory=machine.memory,
        cores=list(range(machine.cpu_count)),
    )
