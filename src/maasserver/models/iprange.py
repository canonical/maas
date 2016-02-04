# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for IPRange.

Specifies all types of IP address ranges MAAS can work with, such as
DHCP ranges and user-reserved ranges.
"""
from maasserver.utils.orm import MAASQueriesMixin
import netaddr
from provisioningserver.utils.network import make_iprange


__all__ = [
    'IPRange',
]

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import (
    CharField,
    ForeignKey,
    PROTECT,
    QuerySet, Manager)
from maasserver.enum import IPRANGE_TYPE_CHOICES
from maasserver.fields import MAASIPAddressField
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from netaddr import (
    AddrFormatError,
    IPAddress,
    IPNetwork,
)
from provisioningserver.logger import get_maas_logger


maaslog = get_maas_logger("iprange")


class IPRangeQueriesMixin(MAASQueriesMixin):

    def get_specifiers_q(self, specifiers, separator=':', **kwargs):
        # Circular imports.

        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            'type': "__type",
            'start_ip': "__start_ip",
            'end_ip': "__end_ip",
        }
        return super(IPRangeQueriesMixin, self).get_specifiers_q(
            specifiers, specifier_types=specifier_types, separator=separator,
            **kwargs)


class IPRangeQuerySet(IPRangeQueriesMixin, QuerySet):
    """Custom QuerySet which mixes in some additional queries specific to
    subnets. This needs to be a mixin because an identical method is needed on
    both the Manager and all QuerySets which result from calling the manager.
    """


class IPRangeManager(Manager, IPRangeQueriesMixin):
    def get_queryset(self):
        queryset = IPRangeQuerySet(self.model, using=self._db)
        return queryset

    def get_iprange_or_404(self, specifiers):
        """Fetch a `Interface` by its `Node`'s system_id and its id.  Raise
        exceptions if no `Interface` with this id exist, if the `Node` with
        system_id doesn't exist, if the `Interface` doesn't exist on the
        `Node`, or if the provided user has not the required permission on
        this `Node` and `Interface`.

        :param specifiers: The interface specifier.
        :type specifiers: str
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        iprange = self.get_object_by_specifiers_or_raise(specifiers)
        return iprange


class IPRange(CleanSave, TimestampedModel):
    """Represents a range of IP addresses used for a particular purpose in
    MAAS, such as a DHCP range or a range of reserved addresses."""

    objects = IPRangeManager()

    subnet = ForeignKey('Subnet', editable=True, blank=False, null=False)

    type = CharField(
        max_length=20, editable=True, choices=IPRANGE_TYPE_CHOICES,
        null=False, blank=False)

    start_ip = MAASIPAddressField(
        null=False, editable=True, blank=False, verbose_name='Start IP')

    end_ip = MAASIPAddressField(
        null=False, editable=True, blank=False, verbose_name='End IP')

    user = ForeignKey(
        User, default=None, blank=True, null=True, editable=True,
        on_delete=PROTECT)

    comment = CharField(
        max_length=255, null=True, blank=True, editable=True)

    def __repr__(self):
        return (
            'IPRange(subnet_id=%r, start_ip=%r, end_ip=%r, type=%r, '
            'user_id=%r, comment=%r)') % (
            self.subnet_id, self.start_ip, self.end_ip, self.type,
            self.user_id, self.comment)

    def clean(self):
        super().clean()
        try:
            # XXX mpontillo 2015-12-22: I would rather the Django model field
            # just give me back an IPAddress, but changing it to do this was
            # had a much larger impact than I expected.
            start_ip = IPAddress(self.start_ip)
            end_ip = IPAddress(self.end_ip)
        except AddrFormatError:
            # This validation will be called even if the start_ip or end_ip
            # field is missing. So we need to check them again here, before
            # proceeding with the validation (and potentially crashing).
            raise ValidationError(
                "Start IP address and end IP address are both required.")
        if end_ip.version != start_ip.version:
            raise ValidationError(
                "Start IP address and end IP address must be in the same "
                "address family.")
        if end_ip < start_ip:
            raise ValidationError(
                "End IP address must not be less than Start IP address.")
        if self.subnet_id is not None:
            cidr = IPNetwork(self.subnet.cidr)
            if start_ip not in cidr and end_ip not in cidr:
                raise ValidationError(
                    "IP addresses must be within subnet: %s." % cidr)
            if start_ip not in cidr:
                raise ValidationError(
                    "Start IP address must be within subnet: %s." % cidr)
            if end_ip not in cidr:
                raise ValidationError(
                    "End IP address must be within subnet: %s." % cidr)

    @property
    def netaddr_iprange(self):
        return netaddr.IPRange(self.start_ip, self.end_ip)

    def get_MAASIPRange(self):
        purpose = self.type
        # Using '-' instead of '_' is just for consistency.
        # APIs in previous MAAS releases used '-' in range types.
        purpose = purpose.replace('_', '-')
        return make_iprange(self.start_ip, self.end_ip, purpose=purpose)
