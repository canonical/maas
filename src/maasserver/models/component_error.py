# Copyright 2012 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Persistent component errors."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    'ComponentError',
    ]


from django.db.models import CharField
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


class ComponentError(CleanSave, TimestampedModel):
    """Error state of a major component of the system."""

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""

    # A descriptor for the failing component, as in the COMPONENT enum.
    # This is a failure state for an out-of-process component.  We won't
    # know much about what's wrong, and we don't support multiple errors
    # for a single component.
    component = CharField(max_length=40, unique=True, blank=False)

    # Human-readable description of what's wrong.
    error = CharField(max_length=1000, blank=False)
