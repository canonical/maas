
# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSResource objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DNSResource",
    "DEFAULT_DNS_TTL",
    "NAME_VALIDATOR",
    ]

import re

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    IntegerField,
    Manager,
    ManyToManyField,
    PROTECT,
)
from django.db.models.query import QuerySet
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.domain import Domain
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin


LABEL = r'[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}'
# only one label allowed
NAMESPEC = r'^%s$' % (LABEL)


def get_default_domain():
    """Get the default domain name."""
    return Domain.objects.get_default_domain().id


def validate_dnsresource_name(value):
    """Django validator: `value` must be a valid DNS Zone name."""
    if value is not None and value != '':
        namespec = re.compile(NAMESPEC)
        if not namespec.search(value):
            raise ValidationError("Invalid dnsresource name: %s." % value)

NAME_VALIDATOR = RegexValidator(NAMESPEC)
DEFAULT_DNS_TTL = 30


class DNSResourceQueriesMixin(MAASQueriesMixin):

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'name': "__name",
            'domain': (Domain.objects, 'domain'),
        }
        return super(DNSResourceQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)


class DNSResourceQuerySet(QuerySet, DNSResourceQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class DNSResourceManager(Manager, DNSResourceQueriesMixin):
    """Manager for :class:`DNSResource` model."""

    def get_queryset(self):
        queryset = DNSResourceQuerySet(self.model, using=self._db)
        return queryset

    def get_dnsresource_or_404(self, specifiers, user, perm):
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


class DNSResource(CleanSave, TimestampedModel):
    """A `DNSResource`.

    :ivar name: The leftmost label for the resource. (No dots.)
    :ivar ttl: Individual TTL for this resource record.
    :ivar domain: Which (forward) DNS zone does this resource go in.
    :ivar ip_addresses: many-to-many linkage to StaticIPAddress
    :ivar objects: An instance of the class :class:`DNSResourceManager`.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "DNSResource"
        verbose_name_plural = "DNSResources"

    objects = DNSResourceManager()

    # If name is blank or None, then we'll use $IFACE.$NODENAME.$DOMAIN (and
    # $NODENAME.$DOMAIN if this is the pxeboot interface), otherwise we'll use
    # only NAME.$DOMAIN.
    name = CharField(
        max_length=63, editable=True, null=True, blank=True, unique=False,
        validators=[validate_dnsresource_name])

    ttl = IntegerField(
        editable=True, null=True, blank=True, default=DEFAULT_DNS_TTL)

    domain = ForeignKey(
        Domain, default=get_default_domain, editable=True,
        on_delete=PROTECT)

    ip_addresses = ManyToManyField(
        'StaticIPAddress', editable=True, blank=True)

    # FUTURE: add RRtype and RHS columns for MX, TXT, abitrary SRV, etc.

    def __unicode__(self):
        return "name=%s" % self.get_name()

    def __str__(self):
        return "name=%s" % self.get_name()

    def get_name(self):
        """Return the name of the dnsresource."""
        return self.name

    def clean(self, *args, **kwargs):
        # make sure that we have a domain
        if self.domain is None or self.domain == '':
            self.domain = Domain.objects.get_default_domain()
        # if we have a name, make sure that it is unique in our dns zone.
        if self.name is not None and self.name != '':
            rrset = DNSResource.objects.filter(
                name=self.name,
                domain=self.domain)
            if rrset.count() > 0 and rrset[0].id != self.id:
                raise ValidationError(
                    "labels must be unique within their zone.")
        super(DNSResource, self).clean(*args, **kwargs)
