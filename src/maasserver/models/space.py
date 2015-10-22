# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Space objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_SPACE_NAME",
    "Space",
    ]

import datetime
import re

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db.models import (
    CharField,
    Manager,
)
from django.shortcuts import get_object_or_404
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


def validate_space_name(value):
    """Django validator: `value` must be either `None`, or valid."""
    if value is None:
        return
    namespec = re.compile('^[ \w-]+$')
    if not namespec.search(value):
        raise ValidationError("Invalid space name: %s." % value)

# Name of the special, default space.  This space cannot be deleted.
DEFAULT_SPACE_NAME = 'space-0'


class SpaceManager(Manager):
    """Manager for :class:`Space` model."""

    def get_default_space(self):
        """Return the default space."""
        now = datetime.datetime.now()
        space, _ = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': None,
                'created': now,
                'updated': now,
            }
        )
        return space

    def get_space_or_404(self, id, user, perm):
        """Fetch a `Space` by its id.  Raise exceptions if no `Space` with
        this id exists or if the provided user has not the required permission
        to access this `Space`.

        :param id: The space_id.
        :type id: int
        :param user: The user that should be used in the permission check.
        :type user: django.contrib.auth.models.User
        :param perm: The permission to assert that the user has on the node.
        :type perm: unicode
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        space = get_object_or_404(self.model, id=id)
        if user.has_perm(perm, space):
            return space
        else:
            raise PermissionDenied()


class Space(CleanSave, TimestampedModel):
    """A `Space`.

    :ivar name: The short-human-identifiable name for this space.
    :ivar objects: An instance of the class :class:`SpaceManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Space"
        verbose_name_plural = "Spaces"

    objects = SpaceManager()

    name = CharField(
        max_length=256, editable=True, null=True, blank=True, unique=False,
        validators=[validate_space_name])

    def __unicode__(self):
        return "name=%s" % self.get_name()

    def is_default(self):
        """Is this the default space?"""
        return self.id == 0

    def get_name(self):
        """Return the name of the space."""
        if self.name:
            return self.name
        else:
            return "space-%s" % self.id

    def clean_name(self):
        reserved = re.compile('space-\d+$')
        if self.name is not None and reserved.search(self.name):
            if (self.id is None or self.name != 'space-%d' % self.id):
                raise ValidationError(
                    {'name': ["Reserved space name."]})

    def clean(self, *args, **kwargs):
        super(Space, self).clean(*args, **kwargs)
        self.clean_name()
