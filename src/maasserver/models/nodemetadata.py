# Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NodeMetadata objects."""

from django.db.models import CASCADE, CharField, ForeignKey, TextField

from maasserver.models.cleansave import CleanSave
from maasserver.models.node import Node
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("nodemetadata")


class NodeMetadata(CleanSave, TimestampedModel):
    """A `NodeMetadata` represents a key/value storage for Node metadata.

    The purpose of NodeMetadata is to be used for descriptive data about
    a Node, to avoid widening the Node table with data that is not
    prescriptive (used by MAAS to actually manage a Node) nor usable outside
    the context of a single Node page.

    :ivar node: `Node` this `NodeMetadata` represents node metadata for.
    :ivar key: A key as a string.
    :ivar value: Value as a string.
    :ivar objects: the switch manager class.
    """

    class Meta:
        verbose_name = "NodeMetadata"
        verbose_name_plural = "NodeMetadata"
        unique_together = ("node", "key")

    node = ForeignKey(
        Node, null=False, blank=False, editable=False, on_delete=CASCADE
    )

    key = CharField(max_length=64, null=False, blank=False)

    value = TextField(null=False, blank=False)

    def __str__(self):
        return "{} ({}/{})".format(
            self.__class__.__name__,
            self.node.hostname,
            self.key,
        )
