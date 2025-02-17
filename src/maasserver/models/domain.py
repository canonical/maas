# Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Domain objects."""

__all__ = [
    "DEFAULT_DOMAIN_NAME",
    "dns_kms_setting_changed",
    "Domain",
    "NAME_VALIDATOR",
    "NAMESPEC",
    "validate_domain_name",
]

from collections import defaultdict, OrderedDict
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    AutoField,
    BooleanField,
    Manager,
    PositiveIntegerField,
    Q,
)
from django.db.models.query import QuerySet
from django.utils import timezone
from netaddr import IPAddress

from maasserver.fields import DomainNameField
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.sqlalchemy import service_layer
from maasserver.utils.orm import MAASQueriesMixin

# Labels are at most 63 octets long, and a name can be many of them.
LABEL = r"[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}"
NAMESPEC = rf"({LABEL}[.])*{LABEL}[.]?"


def validate_domain_name(value):
    """Django validator: `value` must be a valid DNS Zone name."""
    namespec = re.compile(f"^{NAMESPEC}$")
    if len(value) > 255:
        raise ValidationError(
            "Domain name length cannot exceed 255 characters."
        )
    if not namespec.match(value):
        disallowed_chars = re.sub("[a-zA-Z0-9-.]*", "", value)
        if disallowed_chars:
            raise ValidationError("Domain name contains invalid characters.")
        raise ValidationError(f"Invalid domain name: {value}.")
    if value == Config.objects.get_config("maas_internal_domain"):
        raise ValidationError(
            "Domain name cannot duplicate maas internal domain name."
        )


def validate_internal_domain_name(value):
    """Django validator: `value` must be a valid DNS Zone name."""
    namespec = re.compile("^%s$" % NAMESPEC)
    if not namespec.search(value) or len(value) > 255:
        raise ValidationError("Invalid domain name: %s." % value)


NAME_VALIDATOR = RegexValidator("^%s$" % NAMESPEC)

# Name of the special, default domain.  This domain cannot be deleted.
DEFAULT_DOMAIN_NAME = "maas"


def dns_kms_setting_changed():
    """Config.windows_kms_host has changed.

    Update any 'SRV 0 0 1688 ' DNSResource records for _vlmcs._tcp in
    ALL domains.
    """
    kms_host = Config.objects.get_config("windows_kms_host")
    for domain in Domain.objects.filter(authoritative=True):
        domain.update_kms_srv(kms_host)


class DomainQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "name": "__name",
            "id": "__id",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )


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
        # Circular imports.
        from maasserver.models.globaldefault import GlobalDefault

        return GlobalDefault.objects.instance().domain

    def get_forward_domains(self):
        rows = self.raw(
            """SELECT * FROM maasserver_domain domain
            WHERE EXISTS (
                SELECT id FROM maasserver_forwarddnsserver_domains WHERE domain_id = domain.id
            );"""
        )
        return list(rows)

    def get_or_create_default_domain(self):
        """Return the default domain."""
        now = timezone.now()
        domain, _ = self.get_or_create(
            id=0,
            defaults={
                "id": 0,
                "name": DEFAULT_DOMAIN_NAME,
                "authoritative": True,
                "ttl": None,
                "created": now,
                "updated": now,
            },
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

    objects = DomainManager()

    # explicitly define the AutoField since default is BigAutoField and causing
    # modifications causes django to include this in the migration and not
    # allowing 0 as a value
    id = AutoField(primary_key=True, auto_created=True, verbose_name="ID")

    name = DomainNameField(
        max_length=256,
        editable=True,
        null=False,
        blank=False,
        unique=True,
        validators=[validate_domain_name],
    )

    # We manage the forward zone.
    authoritative = BooleanField(
        blank=True, null=True, default=True, db_index=True, editable=True
    )

    # Default TTL for this Domain.
    # If None and not overridden lower, then we will use the global default.
    ttl = PositiveIntegerField(default=None, null=True, blank=True)

    def update_kms_srv(self, kms_host=-1):
        # avoid recursive imports
        from maasserver.models import DNSData, DNSResource

        # Since None and '' are both valid values, we use -1 as the "I want the
        # default value" indicator, and fetch the Config value accordingly.
        if kms_host == -1:
            kms_host = Config.objects.get_config("windows_kms_host")
        if kms_host is None or kms_host == "":
            # No more Config.windows_kms_host, so we need to delete the kms
            # host entries that we may have created.  The for loop is over 0 or
            # 1 DNSResource records
            for dnsrr in self.dnsresource_set.filter(name="_vlmcs._tcp"):
                dnsrr.dnsdata_set.filter(
                    rrtype="SRV", rrdata__startswith="0 0 1688 "
                ).delete()
        else:
            # force kms_host to be an FQDN (with trailing dot.)
            validate_domain_name(kms_host)
            if not kms_host.endswith("."):
                kms_host += "."
            # The windows_kms_host config parameter only manages priority 0,
            # weight 0, port 1688.  To do something different, use the
            # dnsresources api.
            srv_data = "0 0 1688 %s" % kms_host
            dnsrr, _ = DNSResource.objects.get_or_create(
                domain_id=self.id, name="_vlmcs._tcp", defaults={}
            )
            srv, created = DNSData.objects.update_or_create(
                dnsresource_id=dnsrr.id,
                rrtype="SRV",
                rrdata__startswith="0 0 1688 ",
                defaults=dict(rrdata=srv_data),
            )

    def get_base_ttl(self, rrtype, default_ttl):
        # If there is a Resource Record set, which has a non-None TTL, then it
        # wins.  Otherwise our ttl if we have one, or the passed-in default.
        from maasserver.models import DNSData

        rrset = (
            DNSData.objects.filter(rrtype=rrtype, ttl__isnull=False)
            .filter(Q(dnsresource__name="@") | Q(dnsresource__name=""))
            .filter(dnsresource__domain_id=self.id)
        )
        if rrset.exists():
            return rrset.first().ttl
        elif self.ttl is not None:
            return self.ttl
        else:
            return default_ttl

    @property
    def resource_count(self):
        """How many DNSResource names are attached to this domain."""
        from maasserver.models.dnsresource import DNSResource

        return DNSResource.objects.filter(domain_id=self.id).count()

    @property
    def resource_record_count(self):
        """How many total Resource Records come from non-Nodes."""
        count = 0
        for resource in self.dnsresource_set.all():
            count += len(resource.ip_addresses.all())
            count += len(resource.dnsdata_set.all())
        return count

    @property
    def forward_dns_servers(self):
        # avoid circular import
        from maasserver.models.forwarddnsserver import ForwardDNSServer

        return ForwardDNSServer.objects.filter(domains=self)

    def add_delegations(self, mapping, ns_host_name, dns_ip_list, default_ttl):
        """Find any subdomains that need to be added to this domain, and add
        them.

        This function updates the mapping to add delegations and any needed
        glue records for any domains that are descendants of this one.  These
        are not in the database, because they may be multi-lable (foo.bar.maas
        and maas are domains, but bar.maas isn't), and we don't want to allow
        multi-label elements in the model, due to the extreme complexity it
        introduces.
        """

        # Recursive includes.
        from maasserver.models.dnsresource import separate_fqdn

        subdomains = Domain.objects.filter(name__endswith="." + self.name)
        possible = subdomains[:]
        # Anything with an intervening domain should not be delegated from
        # this domain.
        for middle in possible:
            subdomains = subdomains.exclude(name__endswith="." + middle.name)
        for subdomain in subdomains:
            nsttl = subdomain.get_base_ttl("NS", default_ttl)
            ttl = subdomain.get_base_ttl("A", default_ttl)
            # Strip off this domain name from the end of the resource name.
            name = subdomain.name[: -len(self.name) - 1]
            # If we are authoritative for the subdomain, then generate the NS
            # and any needed glue records.  These will automatically be in the
            # child zone.
            if subdomain.authoritative:
                mapping[name].rrset.add((nsttl, "NS", ns_host_name))
                if ns_host_name.endswith("." + self.name):
                    # The ns_host_name lives in a subdomain of this subdomain,
                    # and we are authoritative for that.  We need to add glue
                    # to this subdomain.
                    ns_name = separate_fqdn(ns_host_name, "NS", self.name)[0]
                    for addr in dns_ip_list:
                        if IPAddress(addr).version == 4:
                            mapping[ns_name].rrset.add((ttl, "A", addr))
                        else:
                            mapping[ns_name].rrset.add((ttl, "AAAA", addr))
            # Also return any NS RRset from the dnsdata for the '@' label in
            # that zone.  Add glue records for NS hosts as needed.
            for lhs in subdomain.dnsresource_set.filter(name="@"):
                for data in lhs.dnsdata_set.filter(rrtype="NS"):
                    mapping[name].rrset.add((ttl, data.rrtype, data.rrdata))
                    # Figure out if we need to add glue, and generate it if
                    # needed.
                    if data.rrdata == "@":
                        # This glue is the responsibility of the admin.
                        continue
                    if not data.rrdata.endswith("."):
                        # Non-qualified NSRR, append the domain.
                        fqdn = f"{data.rrdata}.{subdomain.name}."
                    elif not data.rrdata.endswith("%s." % subdomain.name):
                        continue
                    else:
                        # NSRR is an FQDN in or under subdomain.
                        fqdn = data.rrdata
                    # If we get here, then the NS host is in subdomain, or some
                    # subdomain thereof, and is not '@' in the subdomain.
                    # Strip the trailing dot, and split the FQDN.
                    h_name, d_name = separate_fqdn(fqdn[:-1], "NS")
                    # Make sure we look in the right domain for the addresses.
                    if d_name == subdomain.name:
                        nsrrset = subdomain.dnsresource_set.filter(name=h_name)
                    else:
                        nsdomain = Domain.objects.filter(name=d_name)
                        if not nsdomain.exists():
                            continue
                        else:
                            nsdomain = nsdomain[0]
                        nsrrset = nsdomain.dnsresource_set.filter(name=h_name)
                        h_name = fqdn[: -len(subdomain.name) - 2]
                    for nsrr in nsrrset:
                        for addr in nsrr.get_addresses():
                            if IPAddress(addr).version == 4:
                                mapping[h_name].rrset.add((ttl, "A", addr))
                            else:
                                mapping[h_name].rrset.add((ttl, "AAAA", addr))

    def __str__(self):
        return "name=%s" % self.get_name()

    def __unicode__(self):
        return "name=%s" % self.get_name()

    def is_default(self):
        """Returns True if this is the default domain, False otherwise."""
        # Iterate over cached objects. (There should be just one, in fact.)
        for defaults in self.globaldefault_set.all():
            if defaults.domain_id == self.id:
                return True
        return False

    def get_name(self):
        """Return the name of the domain."""
        return self.name

    def delete(self):
        if self.is_default():
            raise ValidationError(
                "This domain is the default domain, it cannot be deleted."
            )
        super().delete()

    def save(self, *args, **kwargs):
        created = self.id is None
        super().save(*args, **kwargs)
        if created:
            self.update_kms_srv()
        # If there is a DNSResource in our parent domain that matches this
        # domain name, the migrate the DNSResource to the new domain.
        parent = Domain.objects.filter(name=".".join(self.name.split(".")[1:]))
        if parent.exists():
            me = parent[0].dnsresource_set.filter(name=self.name.split(".")[0])
            for rr in me:
                rr.name = "@"
                rr.domain = self
                rr.save()

    def clean_name(self):
        # Automatically strip any trailing dot from the domain name.
        if self.name is not None and self.name.endswith("."):
            self.name = self.name[:-1]

    def validate_authority(self):
        if self.authoritative and len(self.forward_dns_servers) > 0:
            raise ValidationError(
                "A Domain cannot be both authoritative and have"
                "forward DNS servers"
            )

    def clean(self, *args, **kwargs):
        super().clean(*args, **kwargs)
        self.clean_name()
        self.validate_authority()

    def render_json_for_related_rrdata(
        self, for_list=False, include_dnsdata=True, as_dict=False, user=None
    ):
        """Render a representation of this domain's related non-IP data,
        suitable for converting to JSON.

        :return: data"""
        from maasserver.models import DNSData

        if include_dnsdata is True:
            rr_mapping = DNSData.objects.get_hostname_dnsdata_mapping(
                self, raw_ttl=True
            )
        else:
            # Circular imports.
            from maasserver.models.dnsdata import HostnameRRsetMapping

            rr_mapping = defaultdict(HostnameRRsetMapping)
        # Smash the IP Addresses in the rrset mapping, so that the far end
        # only needs to worry about one thing.
        ip_mapping = (
            service_layer.services.staticipaddress.get_hostname_ip_mapping(
                int(self.id), raw_ttl=True
            )
        )
        for hostname, info in ip_mapping.items():
            if (
                user is not None
                and not user.is_superuser
                and info.user_id is not None
                and info.user_id != user.id
            ):
                continue
            entry = rr_mapping[hostname[: -len(self.name) - 1]]
            entry.dnsresource_id = info.dnsresource_id
            if info.system_id is not None:
                entry.system_id = info.system_id
                entry.node_type = info.node_type
            if info.user_id is not None:
                entry.user_id = info.user_id
            for ip in info.ips:
                record_type = "AAAA" if IPAddress(ip).version == 6 else "A"
                entry.rrset.add((info.ttl, record_type, ip, None))
        if as_dict is True:
            result = OrderedDict()
        else:
            result = []
        for hostname, info in rr_mapping.items():
            data = [
                {
                    "name": hostname,
                    "system_id": info.system_id,
                    "node_type": info.node_type,
                    "user_id": info.user_id,
                    "dnsresource_id": info.dnsresource_id,
                    "ttl": ttl,
                    "rrtype": rrtype,
                    "rrdata": rrdata,
                    "dnsdata_id": dnsdata_id,
                }
                for ttl, rrtype, rrdata, dnsdata_id in info.rrset
                if (
                    info.user_id is None
                    or user is None
                    or user.is_superuser
                    or (info.user_id is not None and info.user_id == user.id)
                )
            ]
            if as_dict is True:
                existing = result.get(hostname, [])
                existing.extend(data)
                result[hostname] = existing
            else:
                result.extend(data)
        return result
