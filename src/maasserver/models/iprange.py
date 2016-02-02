# Copyright 2015 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for IPRange.

Specifies all types of IP address ranges MAAS can work with, such as
DHCP ranges and user-reserved ranges.
"""
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
)
from maasserver.enum import (
    IPRANGE_TYPE,
    IPRANGE_TYPE_CHOICES,
)
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


class IPRange(CleanSave, TimestampedModel):
    """Represents a range of IP addresses used for a particular purpose in
    MAAS, such as a DHCP range or a range of reserved addresses."""

    subnet = ForeignKey('Subnet', editable=True, blank=False, null=False)

    type = CharField(
        max_length=20, editable=True, choices=IPRANGE_TYPE_CHOICES,
        null=False, blank=False)

    start_ip = MAASIPAddressField(
        null=False, editable=False, blank=False, verbose_name='Start IP')

    end_ip = MAASIPAddressField(
        null=False, editable=False, blank=False, verbose_name='End IP')

    user = ForeignKey(
        User, default=None, blank=True, null=True, editable=False,
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
        if self.user_id is None and self.type == IPRANGE_TYPE.USER_RESERVED:
            raise ValidationError("User-reserved range must specify a user.")
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
