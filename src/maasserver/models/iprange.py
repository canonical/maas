# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for IPRange.

Specifies all types of IP address ranges MAAS can work with, such as
DHCP ranges and user-reserved ranges.
"""

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    GenericIPAddressField,
    Manager,
    PROTECT,
    QuerySet,
)
import netaddr
from netaddr import AddrFormatError, IPAddress, IPNetwork

from maascommon.utils.network import make_iprange
from maascommon.workflows.dhcp import (
    CONFIGURE_DHCP_WORKFLOW_NAME,
    ConfigureDHCPParam,
)
from maasserver.enum import IPRANGE_TYPE, IPRANGE_TYPE_CHOICES
from maasserver.models.cleansave import CleanSave
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import (
    MAASQueriesMixin,
    post_commit_do,
    transactional,
)
from maasserver.workflow import start_workflow
from provisioningserver.logger import get_maas_logger

maaslog = get_maas_logger("iprange")


class IPRangeQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # Circular imports.

        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "type": "__type",
            "start_ip": "__start_ip",
            "end_ip": "__end_ip",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )


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

    subnet = ForeignKey(
        "Subnet", editable=True, blank=False, null=False, on_delete=CASCADE
    )

    type = CharField(
        max_length=20,
        editable=True,
        choices=IPRANGE_TYPE_CHOICES,
        null=False,
        blank=False,
    )

    start_ip = GenericIPAddressField(
        null=False, editable=True, blank=False, verbose_name="Start IP"
    )

    end_ip = GenericIPAddressField(
        null=False, editable=True, blank=False, verbose_name="End IP"
    )

    user = ForeignKey(
        User,
        default=None,
        blank=True,
        null=True,
        editable=True,
        on_delete=PROTECT,
    )

    # In Django 1.8, CharFields with null=True, blank=True had a default
    # of '' (empty string), whereas with at least 1.11 that is None.
    # Force the former behaviour, since the documentation is not very clear
    # on what should happen.
    comment = CharField(
        max_length=255, null=True, blank=True, editable=True, default=""
    )

    def __repr__(self):
        return (
            "IPRange(subnet_id=%r, start_ip=%r, end_ip=%r, type=%r, "
            "user_id=%r, comment=%r)"
        ) % (
            self.subnet_id,
            self.start_ip,
            self.end_ip,
            self.type,
            self.user_id,
            self.comment,
        )

    def __contains__(self, item):
        return item in self.netaddr_iprange

    def _raise_validation_error(self, message, fields=None):
        if fields is None:
            # By default, highlight the start_ip and the end_ip.
            fields = ["start_ip", "end_ip"]
        validation_errors = {}
        for field in fields:
            validation_errors[field] = [message]
        raise ValidationError(validation_errors)

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
            self._raise_validation_error(
                "Start IP address and end IP address are both required."
            )
        if end_ip.version != start_ip.version:
            self._raise_validation_error(
                "Start IP address and end IP address must be in the same "
                "address family."
            )
        if end_ip < start_ip:
            self._raise_validation_error(
                "End IP address must not be less than Start IP address.",
                fields=["end_ip"],
            )
        if self.subnet_id is not None:
            cidr = IPNetwork(self.subnet.cidr)
            if start_ip not in cidr and end_ip not in cidr:
                self._raise_validation_error(
                    "IP addresses must be within subnet: %s." % cidr
                )
            if start_ip not in cidr:
                self._raise_validation_error(
                    "Start IP address must be within subnet: %s." % cidr,
                    fields=["start_ip"],
                )
            if end_ip not in cidr:
                self._raise_validation_error(
                    "End IP address must be within subnet: %s." % cidr,
                    fields=["end_ip"],
                )
            if cidr.network == start_ip:
                self._raise_validation_error(
                    "Reserved network address cannot be included in IP range.",
                    fields=["start_ip"],
                )
            if cidr.version == 4 and cidr.broadcast == end_ip:
                self._raise_validation_error(
                    "Broadcast address cannot be included in IP range.",
                    fields=["end_ip"],
                )
        if (
            start_ip.version == 6
            and self.type == IPRANGE_TYPE.DYNAMIC
            and netaddr.IPRange(start_ip, end_ip).size < 256
        ):
            self._raise_validation_error(
                "IPv6 dynamic range must be at least 256 addresses in size."
            )
        self._validate_duplicates_and_overlaps()

    @property
    def netaddr_iprange(self):
        return netaddr.IPRange(self.start_ip, self.end_ip)

    def get_MAASIPRange(self):
        purpose = self.type
        # Using '-' instead of '_' is just for consistency.
        # APIs in previous MAAS releases used '-' in range types.
        purpose = purpose.replace("_", "-")
        return make_iprange(self.start_ip, self.end_ip, purpose=purpose)

    @transactional
    def _validate_duplicates_and_overlaps(self):
        """Make sure the new or updated range isn't going to cause a conflict.
        If it will, raise ValidationError.
        """
        # Check against the valid types before going further, since whether
        # or not the range overlaps anything that could cause an error heavily
        # depends on its type.
        valid_types = {choice[0] for choice in IPRANGE_TYPE_CHOICES}

        # If model is incomplete, save() will fail, so don't bother checking.
        if (
            self.subnet_id is None
            or self.start_ip is None
            or self.end_ip is None
            or self.type not in valid_types
        ):
            return

        # Reserved ranges can overlap allocated IPs but not other ranges.
        # Dynamic ranges cannot overlap anything (no ranges or IPs).
        if self.type == IPRANGE_TYPE.RESERVED:
            unused = self.subnet.get_ipranges_available_for_reserved_range(
                exclude_ip_range_id=self.id
            )
        else:
            unused = self.subnet.get_ipranges_available_for_dynamic_range(
                exclude_ip_range_id=self.id
            )

        if not unused:
            self._raise_validation_error(
                f"There is no room for any {self.type} ranges on this subnet."
            )

        message = f"Requested {self.type} range conflicts with an existing "
        if self.type == IPRANGE_TYPE.RESERVED:
            message += "range."
        else:
            message += "IP address or range."

        # Find unused range for start_ip
        for unused_range in unused:
            if IPAddress(self.start_ip) in unused_range:
                if IPAddress(self.end_ip) in unused_range:
                    # Success, start and end IP are in an unused range.
                    return
                else:
                    self._raise_validation_error(message)
        self._raise_validation_error(message)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        if self.subnet.vlan.dhcp_on:
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(ip_range_ids=[self.id]),
                task_queue="region",
            )

    def delete(self, *args, **kwargs):
        subnet_id = self.subnet_id
        dhcp_on = self.subnet.vlan.dhcp_on

        super().delete(*args, **kwargs)

        if dhcp_on:
            post_commit_do(
                start_workflow,
                workflow_name=CONFIGURE_DHCP_WORKFLOW_NAME,
                param=ConfigureDHCPParam(subnet_ids=[subnet_id]),
                task_queue="region",
            )
