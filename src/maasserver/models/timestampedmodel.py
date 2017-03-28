# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model base class with creation/update timestamps."""

__all__ = [
    'now',
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


# Having 'object' here should not be required, but it is a workaround for the
# bug in PyCharm described here:
#     https://youtrack.jetbrains.com/issue/PY-12566
class TimestampedModel(Model, object):
    """Abstract base model with creation/update timestamps.

    Timestamps are taken from the database transaction clock.

    :ivar created: Object's creation time.
    :ivar updated: Time of object's latest update.
    """

    class Meta(DefaultMeta):
        abstract = True

    created = DateTimeField(editable=False)
    updated = DateTimeField(editable=False)

    def save(self, _created=None, _updated=None, *args, **kwargs):
        """Set `created` and `updated` before saving.

        If the record is new (its ``id`` is `None`) then `created` is set to
        the current time if it has not already been set. Then `updated` is set
        to the same as `created`.

        If the record already exists, `updated` is set to the current time.
        """
        update_created = False
        update_updated = False
        if self.id is None:
            # New record; set created if not set.
            if self.created is None:
                self.created = now()
            # Set updated to same as created.
            self.updated = self.created
            update_created = True
            update_updated = True
        else:
            # Existing record; set updated always.
            self.updated = now()
            update_updated = True
        # Allow overriding the values before saving, so that these values can
        # be changed in sample data, unit tests, etc.
        if _created is not None:
            self.created = _created
            update_created = True
        if _updated is not None:
            self.updated = _updated
            update_updated = True
            # Ensure consistency.
            if self.updated < self.created:
                self.created = self.updated
                update_created = True
        if 'update_fields' in kwargs:
            if update_created:
                kwargs['update_fields'].append('created')
            if update_updated:
                kwargs['update_fields'].append('updated')
        return super(TimestampedModel, self).save(*args, **kwargs)
