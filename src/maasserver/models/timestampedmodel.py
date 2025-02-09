# Copyright 2012-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model base class with creation/update timestamps."""

from django.db.models import DateTimeField, Model
from django.utils import timezone


def now():
    """Current time."""
    return timezone.now()


class TimestampedModel(Model):
    """Abstract base model with creation/update timestamps.

    Timestamps are taken from the database transaction clock.

    :ivar created: Object's creation time.
    :ivar updated: Time of object's latest update.
    """

    class Meta:
        abstract = True

    created = DateTimeField(editable=False)
    updated = DateTimeField(editable=False)

    def save(self, _created=None, _updated=None, *args, **kwargs):
        """Set `created` and `updated` before saving.

        If the record is new (its ``pk`` is `None`) then `created` is set to
        the current time if it has not already been set. Then `updated` is set
        to the same as `created`.

        If the record already exists, `updated` is set to the current time.
        """
        update_created = False
        update_updated = False
        # OneToOneFields set with primary_key=True are created with a primary
        # key that already exists, so we need to check if the created field
        # was filled in in addition to the primary key check. In addition,
        # a OneToOneField that is the primary key will not have an `id` field,
        # so we use Django's `pk` attribute. This uses indirection to find the
        # real primary key.
        if self.pk is None or (_created is None and self.created is None):
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
        if "update_fields" in kwargs:
            kwargs["update_fields"] = set(kwargs["update_fields"])
            if update_created:
                kwargs["update_fields"].add("created")
            if update_updated:
                kwargs["update_fields"].add("updated")
        return super().save(*args, **kwargs)
