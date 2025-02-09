# Copyright 2017-2022 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""NodeDeviceVPD objects."""

from django.db.models import CASCADE, ForeignKey, Index, Model, TextField

from maasserver.models.cleansave import CleanSave
from maasserver.models.nodedevice import NodeDevice


class NodeDeviceVPD(CleanSave, Model):
    """A `NodeDeviceVPD` represents a key/value storage for NodeDevice metadata.

    The purpose of NodeDeviceVPD is to be used for descriptive data about
    a NodeDevice obtained from VPD, to avoid widening the NodeDevice table with
    data that is not prescriptive.

    :ivar node_device: `NodeDevice` this `NodeDeviceVPD` represents metadata for.
    :ivar key: A key as a string.
    :ivar value: Value as a string.
    :ivar objects: the switch manager class.
    """

    class Meta:
        verbose_name = "NodeDeviceVPD"
        verbose_name_plural = "NodeDeviceVPD"
        unique_together = [("node_device", "key")]
        indexes = [Index(fields=("key", "value"))]

    node_device = ForeignKey(
        NodeDevice, null=False, blank=False, editable=False, on_delete=CASCADE
    )

    key = TextField()
    value = TextField()
