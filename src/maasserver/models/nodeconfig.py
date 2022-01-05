from django.db.models import CASCADE, ForeignKey, TextField

from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.enum import enum_choices


class NODE_CONFIG_TYPE:
    """Type of node configuration."""

    DISCOVERED = "discovered"
    DEPLOYMENT = "deployment"


NODE_CONFIG_TYPE_CHOICES = enum_choices(NODE_CONFIG_TYPE)


class NodeConfig(CleanSave, TimestampedModel):
    class Meta(DefaultMeta):
        unique_together = ["node", "name"]

    name = TextField(
        choices=NODE_CONFIG_TYPE_CHOICES, default=NODE_CONFIG_TYPE.DISCOVERED
    )
    node = ForeignKey("Node", on_delete=CASCADE)


def create_default_nodeconfig(node):
    """Create the `discovered` NodeConfig for a Node."""
    return NodeConfig.objects.create(node=node)
