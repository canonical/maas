# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Space objects."""

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
from django.db.models.query import QuerySet
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin


def validate_space_name(value):
    """Django validator: `value` must be either `None`, or valid."""
    if value is None:
        return
    namespec = re.compile('^[ \w-]+$')
    if not namespec.search(value):
        raise ValidationError("Invalid space name: %s." % value)

# Name of the special, default space.  This space cannot be deleted.
DEFAULT_SPACE_NAME = 'space-0'


class SpaceQueriesMixin(MAASQueriesMixin):

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        # Circular imports.
        from maasserver.models import Subnet

        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'name': "__name",
            'subnet': (Subnet.objects, 'space'),
        }
        return super(SpaceQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)


class SpaceQuerySet(QuerySet, SpaceQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class SpaceManager(Manager, SpaceQueriesMixin):
    """Manager for :class:`Space` model."""

    def get_queryset(self):
        queryset = SpaceQuerySet(self.model, using=self._db)
        return queryset

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

    def get_space_or_404(self, specifiers, user, perm):
        """Fetch a `Space` by its id.  Raise exceptions if no `Space` with
        this id exists or if the provided user has not the required permission
        to access this `Space`.

        :param specifiers: The space specifiers.
        :type specifiers: string
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
        space = self.get_object_by_specifiers_or_raise(specifiers)
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

    def __str__(self):
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
