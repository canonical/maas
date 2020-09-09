__all__ = ["create_default_numanode"]


from django.contrib.postgres.fields import ArrayField
from django.db.models import BigIntegerField, CASCADE, ForeignKey, IntegerField

from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class NUMANode(CleanSave, TimestampedModel):
    """A NUMA node in a Node."""

    node = ForeignKey("Node", editable=False, on_delete=CASCADE)
    index = IntegerField(default=0)
    memory = IntegerField()
    cores = ArrayField(IntegerField(), blank=True)

    class Meta:
        unique_together = [("node", "index")]

    def __repr__(self):
        return f"<NUMANode of {self.index} {self.node!r} cores: {self.cores!r} {self.memory}>"


def create_default_numanode(machine):
    """Create the default "0" NUMA node for a machine."""
    return NUMANode.objects.create(
        node=machine,
        memory=machine.memory,
        cores=list(range(machine.cpu_count)),
    )


class NUMANodeHugepages(CleanSave, TimestampedModel):
    """Hugepages memory for a numa node."""

    numanode = ForeignKey(
        NUMANode,
        editable=False,
        on_delete=CASCADE,
        related_name="hugepages_set",
    )
    page_size = BigIntegerField()
    total = BigIntegerField()

    class Meta:
        unique_together = [("numanode", "page_size")]
