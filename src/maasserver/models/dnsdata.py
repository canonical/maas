# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSData objects."""

import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    PositiveIntegerField,
    TextField,
)
from django.db.models.query import QuerySet

from maascommon.enums.dns import DnsUpdateAction
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.dnsresource import DNSResource
from maasserver.models.domain import validate_domain_name
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin
from provisioningserver.logger import get_maas_logger

CNAME_LABEL = r"[_a-zA-Z0-9]([-_a-zA-Z0-9]{0,62}[_a-zA-Z0-9]){0,1}"
CNAME_SPEC = rf"^({CNAME_LABEL}\.)*{CNAME_LABEL}\.?$"
SUPPORTED_RRTYPES = {"CNAME", "MX", "NS", "SRV", "SSHFP", "TXT"}
INVALID_CNAME_MSG = "Invalid CNAME: Should be '<server>'."
INVALID_MX_MSG = (
    "Invalid MX: Should be '<preference> <server>'."
    " Range for preference is 0-65535."
)
INVALID_SRV_MSG = (
    "Invalid SRV: Should be '<priority> <weight> <port> <server>'."
    " Range for priority, weight, and port are 0-65536."
)
INVALID_SSHFP_MSG = (
    "Invalid SSHFP: Should be '<algorithm> <fptype> <fingerprint>'."
)
CNAME_AND_OTHER_MSG = (
    "CNAME records for a name cannot coexist with non-CNAME records."
)
MULTI_CNAME_MSG = "Only one CNAME can be associated with a name."
DIFFERENT_TTL_MSG = "TTL of %d differs from other resource records TTL of %d."

maaslog = get_maas_logger("node")


def validate_rrtype(value):
    """Django validator: `value` must be a valid DNS RRtype name."""
    if value.upper() not in SUPPORTED_RRTYPES:
        raise ValidationError(
            "%s is not one of %s."
            % (value.upper(), " ".join(SUPPORTED_RRTYPES))
        )


class DNSDataQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {None: self._add_default_query, "name": "__name"}
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )


class DNSDataQuerySet(QuerySet, DNSDataQueriesMixin):
    """Custom QuerySet which mixes in some additional queries specific to
    this object. This needs to be a mixin because an identical method is needed
    on both the Manager and all QuerySets which result from calling the
    manager.
    """


class DNSDataManager(Manager, DNSDataQueriesMixin):
    """Manager for :class:`DNSData` model."""

    def get_dnsdata_or_404(self, specifiers, user, perm):
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
        dnsdata = self.get_object_by_specifiers_or_raise(specifiers)
        if user.has_perm(perm, dnsdata):
            return dnsdata
        else:
            raise PermissionDenied()


class DNSData(CleanSave, TimestampedModel):
    """A `DNSData`.

    :ivar rrtype: Type of resource record
    :ivar rrdata: right-hand side of the DNS Resource Record.
    """

    class Meta:
        verbose_name = "DNSData"
        verbose_name_plural = "DNSData"

    objects = DNSDataManager()

    dnsresource = ForeignKey(
        DNSResource,
        editable=True,
        blank=False,
        null=False,
        help_text="DNSResource which is the left-hand side.",
        on_delete=CASCADE,
    )

    # TTL for this resource.  Should be the same for all records of the same
    # RRType on a given label. (BIND will complain and pick one if they are not
    # all the same.)  If None, then we inherit from the parent Domain, or the
    # global default.
    ttl = PositiveIntegerField(default=None, null=True, blank=True)

    rrtype = CharField(
        editable=True,
        max_length=8,
        blank=False,
        null=False,
        unique=False,
        validators=[validate_rrtype],
        help_text="Resource record type",
    )

    rrdata = TextField(
        editable=True,
        blank=False,
        null=False,
        help_text="Entire right-hand side of the resource record.",
    )

    def __unicode__(self):
        return f"{self.rrtype} {self.rrdata}"

    def __str__(self):
        return f"{self.rrtype} {self.rrdata}"

    @property
    def fqdn(self):
        return self.dnsresource.fqdn

    def clean_rrdata(self, *args, **kwargs):
        """verify that the rrdata matches the spec for the resource
        type.
        """
        self.rrtype = self.rrtype.upper()
        if self.rrtype == "CNAME":
            # Depending on the query, this can be quite a few different
            # things...  Make sure it meets the more general case.
            if re.compile(CNAME_SPEC).search(self.rrdata) is None:
                raise ValidationError(INVALID_CNAME_MSG)
        elif self.rrtype == "SSHFP":
            # SSHFP is <algo> <fptype> <fingerprint>.  Do minimal checking so
            # that we support future algorithms and types.
            spec = re.compile(
                r"^(?P<algo>[0-9]+)\s+(?P<fptype>[0-9]+)\s+(?P<fp>.*)$"
            )
            res = spec.search(self.rrdata)
            if res is None:
                raise ValidationError(INVALID_SSHFP_MSG)
            # No further checking.
        elif self.rrtype == "TXT":
            # TXT is freeform, we simply pass it through
            pass
        elif self.rrtype == "MX":
            spec = re.compile(r"^(?P<pref>[0-9]+)\s+(?P<mxhost>.+)$")
            res = spec.search(self.rrdata)
            if res is None:
                raise ValidationError(INVALID_MX_MSG)
            pref = int(res.groupdict()["pref"])
            mxhost = res.groupdict()["mxhost"]
            if pref < 0 or pref > 65535:
                raise ValidationError(INVALID_MX_MSG)
            validate_domain_name(mxhost)
        elif self.rrtype == "NS":
            validate_domain_name(self.rrdata)
        elif self.rrtype == "SRV":
            spec = re.compile(
                r"^(?P<pri>[0-9]+)\s+(?P<weight>[0-9]+)\s+(?P<port>[0-9]+)\s+"
                r"(?P<target>.*)"
            )
            res = spec.search(self.rrdata)
            if res is None:
                raise ValidationError(INVALID_SRV_MSG)
            srv_host = res.groupdict()["target"]
            pri = int(res.groupdict()["pri"])
            weight = int(res.groupdict()["weight"])
            port = int(res.groupdict()["port"])
            if pri < 0 or pri > 65535:
                raise ValidationError(INVALID_SRV_MSG)
            if weight < 0 or weight > 65535:
                raise ValidationError(INVALID_SRV_MSG)
            if port < 0 or port > 65535:
                raise ValidationError(INVALID_SRV_MSG)
            # srv_host can be '.', in which case "the service is decidedly not
            # available at this domain."  Otherwise, it must be a valid name
            # for an Address RRSet.
            if srv_host != ".":
                validate_domain_name(srv_host)

    def clean(self, *args, **kwargs):
        self.clean_rrdata(*args, **kwargs)
        # Force uppercase for the RR Type names.
        self.rrtype = self.rrtype.upper()
        # make sure that we don't create things that we shouldn't.
        # CNAMEs can only exist as a single resource, and only if there are no
        # other resource records on the name.  See how many CNAME and other
        # items that saving this would create, and reject things if needed.
        if self.id is None:
            cname_exists = DNSData.objects.filter(
                dnsresource_id=self.dnsresource_id, rrtype="CNAME"
            ).exists()
            if self.rrtype == "CNAME":
                other_exists = (
                    DNSData.objects.filter(dnsresource__id=self.dnsresource_id)
                    .exclude(rrtype="CNAME")
                    .exists()
                )
                # account for ipaddresses
                other_exists |= self.dnsresource.ip_addresses.exists()
                if other_exists:
                    raise ValidationError(CNAME_AND_OTHER_MSG)
                elif cname_exists:
                    raise ValidationError(MULTI_CNAME_MSG)
            else:
                if cname_exists:
                    raise ValidationError(CNAME_AND_OTHER_MSG)
            rrset = DNSData.objects.filter(
                rrtype=self.rrtype, dnsresource_id=self.dnsresource.id
            ).exclude(ttl=self.ttl)
            if rrset.exists():
                maaslog.warning(
                    DIFFERENT_TTL_MSG % (self.ttl, rrset.first().ttl)
                )
        super().clean(*args, **kwargs)

    def save(self, *args, **kwargs):
        created = self.id is None

        super().save(*args, **kwargs)

        if self.dnsresource.domain.authoritative:
            dnsrr = self.dnsresource
            domain = dnsrr.domain
            default_ttl = Config.objects.get_config("default_dns_ttl")
            ttl = (
                self.ttl
                if self.ttl
                else self.dnsresource.address_ttl
                if self.dnsresource.address_ttl
                else self.dnsresource.domain.ttl
                if self.dnsresource.domain.ttl
                else default_ttl
            )
            if created:
                DNSPublication.objects.create_for_config_update(
                    source=f"added {self.rrtype} to resource {dnsrr.name} on zone {domain.name}",
                    action=DnsUpdateAction.INSERT_DATA,
                    zone=self.dnsresource.domain.name,
                    label=self.dnsresource.name,
                    rtype=self.rrtype,
                    ttl=ttl,
                )
            else:
                DNSPublication.objects.create_for_config_update(
                    source=f"updated {self.rrtype} in resource {dnsrr.name} on zone {domain.name}",
                    action=DnsUpdateAction.UPDATE_DATA,
                    zone=self.dnsresource.domain.name,
                    label=self.dnsresource.name,
                    rtype=self.rrtype,
                    ttl=ttl,
                )

    def delete(self, *args, **kwargs):
        if self.dnsresource.domain.authoritative:
            dnsrr = self.dnsresource
            domain = dnsrr.domain
            default_ttl = Config.objects.get_config("default_dns_ttl")
            ttl = (
                self.ttl
                if self.ttl
                else self.dnsresource.address_ttl
                if self.dnsresource.address_ttl
                else self.dnsresource.domain.ttl
                if self.dnsresource.domain.ttl
                else default_ttl
            )
            DNSPublication.objects.create_for_config_update(
                source=f"removed {self.rrtype} from resource {dnsrr.name} on zone {domain.name}",
                action=DnsUpdateAction.DELETE,
                zone=self.dnsresource.domain.name,
                label=self.dnsresource.name,
                rtype=self.rrtype,
                ttl=ttl,
            )

        super().delete(*args, **kwargs)
