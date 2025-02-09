# Copyright 2014-2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

""":class:`EventType` and friends."""

import logging

from django.db.models import CharField, IntegerField, Manager

from maascommon.events import AUDIT
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel

# Describes how the log levels are displayed in the UI.
LOGGING_LEVELS = {
    AUDIT: "AUDIT",
    logging.DEBUG: "DEBUG",
    logging.INFO: "INFO",
    logging.WARNING: "WARNING",
    logging.ERROR: "ERROR",
    logging.CRITICAL: "CRITICAL",
}

LOGGING_LEVELS_BY_NAME = {
    "AUDIT": AUDIT,
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class EventTypeManager(Manager):
    """A utility to manage the collection of Events."""

    def register(self, name, description, level):
        """Register EventType if it does not exist.

        If the event type already exists the description and level are NOT
        updated with new values. This method is meant to be a just-in-time way
        of creating event types from a predefined and static catalog.
        """
        event_type, _ = self.get_or_create(
            name=name, defaults={"description": description, "level": level}
        )
        return event_type


class EventType(CleanSave, TimestampedModel):
    """A type for events.

    :ivar name: The event type's identifier.
    :ivar description: A human-readable description of the event type.
    :ivar level: Severity of the event.  These match the standard
        Python log levels; higher values are more significant.
    """

    name = CharField(max_length=255, unique=True, blank=False, editable=False)

    description = CharField(max_length=255, blank=False, editable=False)

    level = IntegerField(blank=False, editable=False, db_index=True)

    objects = EventTypeManager()

    @property
    def level_str(self):
        """A human-readable version of the log level."""
        return LOGGING_LEVELS[self.level]

    class Meta:
        verbose_name = "Event type"

    def __str__(self):
        return "{} (level={}, description={})".format(
            self.name,
            self.level,
            self.description,
        )

    def validate_unique(self, exclude=None):
        """Override validate unique so nothing is validated.

        Allow Postgresql to perform the unqiue validation, Django doesn't
        need to perform this work.
        """
        pass
