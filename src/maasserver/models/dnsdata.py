# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSData objects."""

from collections import defaultdict
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection
from django.db.models import (
    CASCADE,
    CharField,
    ForeignKey,
    Manager,
    PositiveIntegerField,
    TextField,
)
from django.db.models.query import QuerySet

from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
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


class HostnameRRsetMapping:
    """This is used to return non-address information for a hostname in a way
    that keeps life simple for the callers.  Rrset is a set of (ttl, rrtype,
    rrdata) tuples."""

    def __init__(
        self,
        system_id=None,
        rrset: set = None,
        node_type=None,
        dnsresource_id=None,
        user_id=None,
    ):
        self.system_id = system_id
        self.node_type = node_type
        self.dnsresource_id = dnsresource_id
        self.user_id = user_id
        self.rrset = set() if rrset is None else rrset.copy()

    def __repr__(self):
        return "HostnameRRSetMapping({!r}, {!r}, {!r}, {!r}, {!r})".format(
            self.system_id,
            self.rrset,
            self.node_type,
            self.dnsresource_id,
            self.user_id,
        )

    def __eq__(self, other):
        return self.__dict__ == other.__dict__


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

    def get_hostname_dnsdata_mapping(
        self, domain, raw_ttl=False, with_ids=True
    ):
        """Return hostname to RRset mapping for this domain."""
        cursor = connection.cursor()
        default_ttl = "%d" % Config.objects.get_config("default_dns_ttl")
        if raw_ttl:
            ttl_clause = """dnsdata.ttl"""
        else:
            ttl_clause = (
                """
                COALESCE(
                    dnsdata.ttl,
                    domain.ttl,
                    %s)"""
                % default_ttl
            )
        sql_query = (
            """
            SELECT
                dnsresource.id,
                dnsresource.name,
                domain.name,
                node.system_id,
                node.node_type,
                node.user_id,
                dnsdata.id,
                """
            + ttl_clause
            + """ AS ttl,
                dnsdata.rrtype,
                dnsdata.rrdata
            FROM maasserver_dnsdata AS dnsdata
            JOIN maasserver_dnsresource AS dnsresource ON
                dnsdata.dnsresource_id = dnsresource.id
            JOIN maasserver_domain as domain ON
                dnsresource.domain_id = domain.id
            LEFT JOIN
                (
                    /* Create a "node" that has the fields we care about and
                     * also has a "fqdn" field.
                     * The fqdn requires that we fetch domain[node.domain_id]
                     * which, in turn, means that we need this inner select.
                     */
                    SELECT
                        nd.hostname AS hostname,
                        nd.system_id AS system_id,
                        nd.node_type AS node_type,
                        nd.owner_id AS user_id ,
                        nd.domain_id AS domain_id,
                        CONCAT(nd.hostname, '.', dom.name) AS fqdn
                    FROM maasserver_node AS nd
                    JOIN maasserver_domain AS dom ON
                        nd.domain_id = dom.id
                ) AS node ON (
                    /* We get the various node fields in the final result for
                     * any resource records that have an FQDN equal to the
                     * respective node.  Because of how names at the top of a
                     * domain are handled (we hide the fact from the user and
                     * put the node in the parent domain, but all the actual
                     * data lives in the child domain), we need to merge the
                     * two views of the world.
                     * If either this is the right node (node name and domain
                     * match, or dnsresource name is '@' and the node fqdn is
                     * the domain name), then we include the information about
                     * the node.
                     */
                    (
                        dnsresource.name = node.hostname AND
                        dnsresource.domain_id = node.domain_id
                    ) OR
                    (
                        dnsresource.name = '@' AND
                        node.fqdn = domain.name
                    )
                )
            WHERE
                /* The entries must be in this domain (though node.domain_id
                 * may be out-of-domain and that's OK.
                 * Additionally, if there is a CNAME and a node, then the node
                 * wins, and we drop the CNAME until the node no longer has the
                 * same name.
                 */
                (dnsresource.domain_id = %s OR node.fqdn IS NOT NULL) AND
                (dnsdata.rrtype != 'CNAME' OR node.fqdn IS NULL)
            ORDER BY
                dnsresource.name,
                dnsdata.rrtype,
                dnsdata.rrdata
            """
        )
        # N.B.: The "node.hostname IS NULL" above is actually checking that
        # no node exists with the same name, in order to make sure that we do
        # not spill CNAME and other data.
        mapping = defaultdict(HostnameRRsetMapping)
        cursor.execute(sql_query, (domain.id,))
        for (
            dnsresource_id,
            name,
            d_name,
            system_id,
            node_type,
            user_id,
            dnsdata_id,
            ttl,
            rrtype,
            rrdata,
        ) in cursor.fetchall():
            if name == "@" and d_name != domain.name:
                name, d_name = d_name.split(".", 1)
                # Since we don't allow more than one label in dnsresource
                # names, we should never ever be wrong in this assertion.
                assert d_name == domain.name, (
                    "Invalid domain; expected '{}' == '{}'".format(
                        d_name,
                        domain.name,
                    )
                )
            entry = mapping[name]
            entry.node_type = node_type
            entry.system_id = system_id
            entry.user_id = user_id
            if with_ids:
                entry.dnsresource_id = dnsresource_id
                rrtuple = (ttl, rrtype, rrdata, dnsdata_id)
            else:
                rrtuple = (ttl, rrtype, rrdata)
            entry.rrset.add(rrtuple)
        return mapping


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
