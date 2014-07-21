# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`Event` and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'Event',
    ]


from django.db.models import ForeignKey
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class Event(CleanSave, TimestampedModel):
    """An `Event` represents a MAAS event.

    :ivar type: The event's type.
    :ivar node: The node of the event.
    """

    type = ForeignKey('EventType', null=False, editable=False)

    node = ForeignKey('Node', null=False, editable=False)

    class Meta(DefaultMeta):
        verbose_name = "Event record"

    def __unicode__(self):
        return "%s (node=%s, type=%s, created=%s)" % (
            self.id, self.node, self.type.name, self.created)
