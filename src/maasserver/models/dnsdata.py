# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSData objects."""

from __future__ import (
    absolute_import,
    print_function,
    unicode_literals,
    )

str = None

__metaclass__ = type
__all__ = [
    "DNSData",
    ]

import re

from django.core.exceptions import (
    PermissionDenied,
    ValidationError,
)
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    PositiveIntegerField,
    TextField,
)
from maasserver import DefaultMeta
from maasserver.models.cleansave import CleanSave
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import validate_domain_name
from maasserver.models.timestampedmodel import TimestampedModel
from provisioningserver.logger import get_maas_logger


CNAME_LABEL = r'[_a-zA-Z0-9]([-_a-zA-Z0-9]{0,62}[_a-zA-Z0-9]){0,1}'
CNAME_SPEC = r'^(%s\.)*%s\.?$' % (CNAME_LABEL, CNAME_LABEL)
SUPPORTED_RRTYPES = {'CNAME', 'MX', 'NS', 'SRV', 'TXT'}
INVALID_CNAME_MSG = "Invalid CNAME: Should be '<server>'."
INVALID_MX_MSG = (
    "Invalid MX: Should be '<preference> <server>'."
    " Range for preference is 0-65535.")
INVALID_SRV_MSG = (
    "Invalid SRV: Should be '<priority> <weight> <port> <server>'."
    " Range for priority, weight, and port are 0-65536.")
CNAME_AND_OTHER_MSG = (
    "CNAME records for a name cannot coexist with non-CNAME records.")
MULTI_CNAME_MSG = "Only one CNAME can be associated with a name."
DIFFERENT_TTL_MSG = "TTL of %d differs from other resource records TTL of %d."

maaslog = get_maas_logger("node")


def validate_rrtype(value):
    """Django validator: `value` must be a valid DNS RRtype name."""
    if value.upper() not in SUPPORTED_RRTYPES:
        raise ValidationError(
            "%s is not one of %s." %
            (value.upper(), " ".join(SUPPORTED_RRTYPES)))


class DNSDataManager(Manager):
    """Manager for :class:`DNSData` model."""

    def get_dnsdata_or_404(self, id, user, perm):
        """Fetch `DNSData` by its id.  Raise exceptions if no `DNSData` with
        this id exists or if the provided user has not the required permission
        to access this `DNSData`.

        :param id:  The ID of the record.
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
        dnsdata = DNSData.objects.get(id=id)
        if user.has_perm(perm, dnsdata):
            return dnsdata
        else:
            raise PermissionDenied()


class DNSData(CleanSave, TimestampedModel):
    """A `DNSData`.

    :ivar resource_type: Type of resource record
    :ivar resource_data: right-hand side of the DNS Resource Record.
    """

    class Meta(DefaultMeta):
        """Needed for South to recognize this model."""
        verbose_name = "DNSData"
        verbose_name_plural = "DNSData"

    objects = DNSDataManager()

    dnsresource = ForeignKey(
        DNSResource, editable=True, blank=False, null=False,
        help_text="DNSResource which is the left-hand side.",
        on_delete=CASCADE)

    # TTL for this resource.  Should be the same for all records of the same
    # RRType on a given label. (BIND will complain and pick one if they are not
    # all the same.)  If None, then we inherit from the parent Domain, or the
    # global default.
    ttl = PositiveIntegerField(default=None, null=True, blank=True)

    resource_type = CharField(
        editable=True, max_length=8, blank=False, null=False, unique=False,
        validators=[validate_rrtype], help_text="Resource record type")

    resource_data = TextField(
        editable=True, blank=False, null=False,
        help_text="Entire right-hand side of the resource record.")

    def __unicode__(self):
        return "%s %s" % (self.resource_type, self.resource_data)

    def __str__(self):
        return "%s %s" % (self.resource_type, self.resource_data)

    def clean_resource_data(self, *args, **kwargs):
        """verify that the resource_data matches the spec for the resource
        type.
        """
        self.resource_type = self.resource_type.upper()
        if self.resource_type == "CNAME":
            # Depending on the query, this can be quite a few different
            # things...  Make sure it meets the more general case.
            if re.compile(CNAME_SPEC).search(self.resource_data) is None:
                raise ValidationError(INVALID_CNAME_MSG)
        elif self.resource_type == "TXT":
            # TXT is freeform, we simply pass it through
            pass
        elif self.resource_type == "MX":
            spec = re.compile(r"^(?P<pref>[0-9])+\s+(?P<mxhost>.+)$")
            res = spec.search(self.resource_data)
            if res is None:
                raise ValidationError(INVALID_MX_MSG)
            pref = int(res.groupdict()['pref'])
            mxhost = res.groupdict()['mxhost']
            if pref < 0 or pref > 65535:
                raise ValidationError(INVALID_MX_MSG)
            validate_domain_name(mxhost)
        elif self.resource_type == "NS":
            validate_domain_name(self.resource_data)
        elif self.resource_type == "SRV":
            spec = re.compile(
                r"^(?P<pri>[0-9]+)\s+(?P<weight>[0-9]+)\s+(?P<port>[0-9]+)\s+"
                r"(?P<target>.*)")
            res = spec.search(self.resource_data)
            srv_host = res.groupdict()['target']
            if res is None:
                raise ValidationError(INVALID_SRV_MSG)
            pri = int(res.groupdict()['pri'])
            weight = int(res.groupdict()['weight'])
            port = int(res.groupdict()['port'])
            if pri < 0 or pri > 65535:
                raise ValidationError(INVALID_SRV_MSG)
            if weight < 0 or weight > 65535:
                raise ValidationError(INVALID_SRV_MSG)
            if port < 0 or port > 65535:
                raise ValidationError(INVALID_SRV_MSG)
            # srv_host can be '.', in which case "the service is decidedly not
            # available at this domain."  Otherwise, it must be a valid name
            # for an Address RRSet.
            if srv_host != '.':
                validate_domain_name(srv_host)

    def clean(self, *args, **kwargs):
        self.clean_resource_data(*args, **kwargs)
        # Force uppercase for the RR Type names.
        self.resource_type = self.resource_type.upper()
        # make sure that we don't create things that we shouldn't.
        # CNAMEs can only exist as a single resource, and only if there are no
        # other resource records on the name.  See how many CNAME and other
        # items that saving this would create, and reject things if needed.
        if self.id is None:
            num_cname = DNSData.objects.filter(
                dnsresource_id=self.dnsresource_id,
                resource_type="CNAME").count()
            if self.resource_type == "CNAME":
                num_other = DNSData.objects.filter(
                    dnsresource__id=self.dnsresource_id).exclude(
                    resource_type="CNAME").count()
                # account for ipaddresses
                num_other += self.dnsresource.ip_addresses.count()
                if num_other > 0:
                    raise ValidationError(CNAME_AND_OTHER_MSG)
                elif num_cname > 0:
                    raise ValidationError(MULTI_CNAME_MSG)
            else:
                if num_cname > 0:
                    raise ValidationError(CNAME_AND_OTHER_MSG)
            rrset = DNSData.objects.filter(
                resource_type=self.resource_type,
                dnsresource_id=self.dnsresource.id).exclude(
                ttl=self.ttl)
            if rrset.count() > 0:
                maaslog.warning(
                    DIFFERENT_TTL_MSG % (self.ttl, rrset.first().ttl))
        super().clean(*args, **kwargs)
