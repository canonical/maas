# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`NodeCommissionResult` model."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'NodeCommissionResult',
    ]


from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    )
from django.shortcuts import get_object_or_404
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from metadataserver import DefaultMeta
from metadataserver.enum import (
    COMMISSIONING_STATUS,
    COMMISSIONING_STATUS_CHOICES,
    )


class NodeCommissionResultManager(Manager):
    """Utility to manage a collection of :class:`NodeCommissionResult`s."""

    def clear_results(self, node):
        """Remove all existing results for a node."""
        self.filter(node=node).delete()

    def store_data(self, node, name, status, data):
        """Store data about a node."""
        existing, created = self.get_or_create(
            node=node, name=name,
            defaults=dict(status=status, data=data))
        if not created:
            existing.data = data
            existing.save()

    def get_data(self, node, name):
        """Get data about a node."""
        ncr = get_object_or_404(NodeCommissionResult, node=node, name=name)
        return ncr.data


class NodeCommissionResult(CleanSave, TimestampedModel):
    """Storage for data returned from node commissioning.

    Commissioning a node results in various bits of data that need to be
    stored, such as lshw output.  This model allows storing of this data
    as unicode text, with an arbitrary name, for later retrieval.

    :ivar node: The context :class:`Node`.
    :ivar status: If this data results from the execution of a script, this
        is the status of this execution.  This can be "OK", "FAILED" or
        "WORKING" for progress reports.
    :ivar name: A unique name to use for the data being stored.
    :ivar data: The file's actual data, unicode only.
    """

    class Meta(DefaultMeta):
        unique_together = ('node', 'name')

    objects = NodeCommissionResultManager()

    node = ForeignKey(
        'maasserver.Node', null=False, editable=False, unique=False)
    status = CharField(
        max_length=100, unique=False, editable=False,
        choices=COMMISSIONING_STATUS_CHOICES,
        default=COMMISSIONING_STATUS.DEFAULT_STATUS)
    name = CharField(max_length=255, unique=False, editable=False)
    data = CharField(max_length=1024 * 1024, editable=True)
