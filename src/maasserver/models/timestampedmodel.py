# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model base class with creation/update timestamps."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'TimestampedModel',
    ]


from django.db import connection
from django.db.models import (
    DateTimeField,
    Model,
    )
from maasserver import DefaultMeta


def now():
    """Current database time (as per start of current transaction)."""
    cursor = connection.cursor()
    cursor.execute("select now()")
    return cursor.fetchone()[0]


class TimestampedModel(Model):
    """Abstract base model with creation/update timestamps.

    Timestamps are taken from the database transaction clock.

    :ivar created: Object's creation time.
    :ivar updated: Time of object's latest update.
    """

    class Meta(DefaultMeta):
        abstract = True

    created = DateTimeField(editable=False)
    updated = DateTimeField(editable=False)

    def save(self, *args, **kwargs):
        current_time = now()
        if self.id is None:
            self.created = current_time
        self.updated = current_time
        return super(TimestampedModel, self).save(*args, **kwargs)
