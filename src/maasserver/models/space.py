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
    "SPACE_NAME_VALIDATOR",
    ]

import datetime

from django.core.exceptions import PermissionDenied
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    Manager,
)
from django.shortcuts import get_object_or_404
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel


SPACE_NAME_VALIDATOR = RegexValidator('^[ \w-]+$')

# Name of the special, default space.  This space cannot be deleted.
DEFAULT_SPACE_NAME = 'Default space'


class SpaceManager(Manager):
    """Manager for :class:`Space` model."""

    def get_default_space(self):
        """Return the default space."""
        now = datetime.datetime.now()
        space, _ = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_SPACE_NAME,
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
        max_length=256, unique=True, editable=True,
        validators=[SPACE_NAME_VALIDATOR])

    def __unicode__(self):
        return "name=%s" % self.name

    def is_default(self):
        """Is this the default space?"""
        return self.id == 0
