# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Domain objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DEFAULT_DOMAIN_NAME",
    "Domain",
    "NAME_VALIDATOR",
    "validate_domain_name",
    ]

import datetime
import re

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import RegexValidator
from django.db.models import (
    Manager,
    NullBooleanField,
)
from django.db.models.query import QuerySet
from maasserver import DefaultMeta
from maasserver.fields import DomainNameField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin

# Labels are at most 63 octets long, and a name can be many of them.
LABEL = r'[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}'
NAMESPEC = r'^(%s\.)*%s\.?$' % (LABEL, LABEL)


def validate_domain_name(value):
    """Django validator: `value` must be a valid DNS Zone name."""
    namespec = re.compile(NAMESPEC)
    if not namespec.search(value) or len(value) > 255:
        raise ValidationError("Invalid domain name: %s." % value)

NAME_VALIDATOR = RegexValidator(NAMESPEC)

# Name of the special, default domain.  This domain cannot be deleted.
DEFAULT_DOMAIN_NAME = 'maas'


class DomainQueriesMixin(MAASQueriesMixin):

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'name': "__name",
            'id': "__id",
        }
        return super(DomainQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)


class DomainQuerySet(QuerySet, DomainQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class DomainManager(Manager, DomainQueriesMixin):
    """Manager for :class:`Domain` model."""

    def get_queryset(self):
        queryset = DomainQuerySet(self.model, using=self._db)
        return queryset

    def get_default_domain(self):
        """Return the default domain."""
        now = datetime.datetime.now()
        domain, created = self.get_or_create(
            id=0,
            defaults={
                'id': 0,
                'name': DEFAULT_DOMAIN_NAME,
                'authoritative': True,
                'created': now,
                'updated': now,
            }
        )
        return domain

    def get_domain_or_404(self, specifiers, user, perm):
        """Fetch a `Domain` by its id.  Raise exceptions if no `Domain` with
        this id exist or if the provided user has not the required permission
        to access this `Domain`.

        :param specifiers: The domain specifiers.
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
        domain = self.get_object_by_specifiers_or_raise(specifiers)
        if user.has_perm(perm, domain):
            return domain
        else:
            raise PermissionDenied()


class Domain(CleanSave, TimestampedModel):
    """A `Domain`.

    :ivar name: The DNS stuffix for this zone
    :ivar authoritative: MAAS manages this (forward) DNS zone.
    :ivar objects: An instance of the class :class:`DomainManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "Domain"
        verbose_name_plural = "Domains"

    objects = DomainManager()

    name = DomainNameField(
        max_length=256, editable=True, null=False, blank=False, unique=True,
        validators=[validate_domain_name])

    # We manage the forward zone.
    authoritative = NullBooleanField(
        default=True, db_index=True, editable=True)

    def __str__(self):
        return "name=%s" % self.get_name()

    def __unicode__(self):
        return "name=%s" % self.get_name()

    def is_default(self):
        """Is this the default domain?"""
        return self.id == 0

    def get_name(self):
        """Return the name of the domain."""
        return self.name

    def resource_count(self):
        """How many nodes are attached to this zone."""
        from maasserver.models.dnsresource import DNSResource
        return DNSResource.objects.filter(domain=self).count()

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This domain is the default domain, it cannot be deleted.")
        super(Domain, self).delete()

    def save(self, *args, **kwargs):
        super(Domain, self).save(*args, **kwargs)

    def clean_name(self):
        # Automatically strip any trailing dot from the domain name.
        if self.name is not None and self.name.endswith('.'):
            self.name = self.name[:-1]

    def clean(self, *args, **kwargs):
        super(Domain, self).clean(*args, **kwargs)
        self.clean_name()
