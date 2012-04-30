# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Utility base class with common model fields."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

__metaclass__ = type
__all__ = [
    'CommonInfo',
    ]


from django.db import models
from maasserver import DefaultMeta


class CommonInfo(models.Model):
    """A base model which:
    - calls full_clean before saving the model (by default).
    - records the creation date and the last modification date.

    :ivar created: The creation date.
    :ivar updated: The last modification date.

    This class has no database table of its own.  Its fields are incorporated
    in the tables of derived classes.
    """

    class Meta(DefaultMeta):
        abstract = True

    created = models.DateTimeField(editable=False)
    updated = models.DateTimeField(editable=False)

    def save(self, skip_check=False, *args, **kwargs):
        # Avoid circular imports.
        from maasserver.models import now

        date_now = now()
        if not self.id:
            self.created = date_now
        self.updated = date_now
        if not skip_check:
            self.full_clean()
        return super(CommonInfo, self).save(*args, **kwargs)
