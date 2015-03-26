# Copyright 2014 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`EventType` and friends."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'EventType',
    ]


import logging

from django.db import (
    IntegrityError,
    transaction,
)
from django.db.models import (
    CharField,
    IntegerField,
    Manager,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import request_transaction_retry

# Describes how the log levels are displayed in the UI.
LOGGING_LEVELS = {
    logging.DEBUG: 'DEBUG',
    logging.INFO: 'INFO',
    logging.WARNING: 'WARNING',
    logging.ERROR: 'ERROR',
    logging.CRITICAL: 'CRITICAL',
}


class EventTypeManager(Manager):
    """A utility to manage the collection of Events."""

    def register(self, name, description, level):
        """Register EventType if it does not exist."""
        try:
            # Attempt to create the event type in a nested transaction so that
            # we can continue using the outer transaction even if this breaks.
            with transaction.atomic():
                return self.create(
                    name=name, description=description, level=level)
        except IntegrityError:
            # We may be in a situation where the event type already existed,
            # or that another session has created the event type concurrently
            # with this thread. Proceed on that assumption.
            try:
                return self.get(name=name)
            except EventType.DoesNotExist:
                # PostgreSQL's indexes do not grok MVCC. Another session has
                # created this event-type, but we cannot see it yet in this
                # session. We need to retry the whole transaction.
                request_transaction_retry()


class EventType(CleanSave, TimestampedModel):
    """A type for events.

    :ivar name: The event type's identifier.
    :ivar description: A human-readable description of the event type.
    :ivar level: Severity of the event.  These match the standard
        Python log levels; higher values are more significant.
    """

    name = CharField(
        max_length=255, unique=True, blank=False, editable=False)

    description = CharField(max_length=255, blank=False, editable=False)

    level = IntegerField(blank=False, editable=False, db_index=True)

    objects = EventTypeManager()

    @property
    def level_str(self):
        """A human-readable version of the log level."""
        return LOGGING_LEVELS[self.level]

    class Meta(DefaultMeta):
        verbose_name = "Event type"

    def __unicode__(self):
        return "%s (level=%s, description=%s)" % (
            self.name, self.level, self.description)

    def full_clean(self, exclude=None, validate_unique=False):
        """Up-call, suppressing check for uniqueness before inserting."""
        return super(EventType, self).full_clean(
            exclude=exclude, validate_unique=validate_unique)
