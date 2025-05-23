# Copyright 2015-2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""DNSResource objects."""

__all__ = [
    "DNSResource",
    "DEFAULT_DNS_TTL",
    "NAME_VALIDATOR",
    "separate_fqdn",
    "validate_dnsresource_name",
]

from functools import cached_property
import re

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.validators import RegexValidator
from django.db.models import (
    CharField,
    ForeignKey,
    Manager,
    ManyToManyField,
    PositiveIntegerField,
    PROTECT,
)
from django.db.models.fields.related_descriptors import (
    create_forward_many_to_many_manager,
    ManyToManyDescriptor,
)
from django.db.models.query import QuerySet
from netaddr import IPAddress

from maascommon.enums.dns import DnsUpdateAction
from maasserver.enum import IPADDRESS_TYPE
from maasserver.models import domain
from maasserver.models.cleansave import CleanSave
from maasserver.models.config import Config
from maasserver.models.dnspublication import DNSPublication
from maasserver.models.domain import Domain
from maasserver.models.node import Node
from maasserver.models.staticipaddress import StaticIPAddress
from maasserver.models.timestampedmodel import TimestampedModel
from maasserver.utils.orm import MAASQueriesMixin
from provisioningserver.logger import LegacyLogger

log = LegacyLogger()


LABEL = r"[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}"
SRV_LABEL = r"_[a-zA-Z0-9]([-a-zA-Z0-9]{0,62}[a-zA-Z0-9]){0,1}"
# SRV RRdata gets name=_SERVICE._PROTO.LABEL, otherwise, only one label
# allowed.
SRV_LHS = f"{SRV_LABEL}.{SRV_LABEL}(.{LABEL})?"
NAMESPEC = r"%s" % LABEL
NAME_VALIDATOR = RegexValidator(NAMESPEC)
DEFAULT_DNS_TTL = 30
SPECIAL_NAMES = ("", "@", "*")


def get_default_domain():
    """Get the default domain name."""
    return Domain.objects.get_default_domain().id


def validate_dnsresource_name(value, rrtype):
    """Django validator: `value` must be a valid DNS Zone name."""
    if value is not None and value not in SPECIAL_NAMES:
        if rrtype == "SRV":
            namespec = re.compile("^%s$" % SRV_LHS)
        else:
            namespec = re.compile("^%s$" % NAMESPEC)
        if not namespec.search(value):
            raise ValidationError("Invalid dnsresource name: %s." % value)


def separate_fqdn(fqdn, rrtype=None, domainname=None):
    """Separate an fqdn based on resource type.

    :param fqdn: Fully qualified domain name, blank, or "@".
    :param rrtype: resource record type. (May be None.)
    :param domainname: If specified, force the fqdn to be in this domain,
    otherwise return ('@', fqdn) if the fqdn is a domain name.

    Returns (name, domain) where name is appropriate for the resource record in
    the domain.
    """
    if fqdn is None or fqdn in SPECIAL_NAMES:
        return (fqdn, None)
    if domainname is not None:
        if domainname == fqdn:
            return ("@", fqdn)
        else:
            # strip off the passed in ".$domainname" from the fqdn.
            name = fqdn[: -len(domainname) - 1]
            return (name, domainname)
    else:
        if Domain.objects.filter(name=fqdn).exists():
            return ("@", fqdn)
    if rrtype == "SRV":
        spec = SRV_LHS
    else:
        spec = LABEL
    regexp = rf"^(?P<name>{spec}).(?P<domain>{domain.NAMESPEC})$"
    regex = re.compile(regexp)
    result = regex.search(fqdn)
    if result is not None:
        answer = result.groupdict()
        return (answer["name"], answer["domain"])
    else:
        return None


class DNSResourceQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: self._add_default_query,
            "name": "__name",
            "domain": (Domain.objects, "domain"),
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )


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

        :param specifiers: The dnsresource specifiers.
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
        dnsresource = self.get_object_by_specifiers_or_raise(specifiers)
        if user.has_perm(perm, dnsresource):
            return dnsresource
        else:
            raise PermissionDenied()


def dnsresource_ip_addresses_manager_factory(superclass, rel, reverse):
    manager = create_forward_many_to_many_manager(superclass, rel, reverse)

    class DNSResourceIPAddressesManager(manager):
        def add(self, *args, **kwargs):
            if len(args) > 0:
                if isinstance(self.instance, DNSResource):
                    dnsrr = self.instance
                    sip = (
                        args[0]
                        if isinstance(args[0], StaticIPAddress)
                        else None
                    )
                elif isinstance(self.instance, StaticIPAddress):
                    dnsrr = (
                        args[0] if isinstance(args[0], DNSResource) else None
                    )
                    sip = self.instance

                if dnsrr:
                    domain = dnsrr.domain
                    if domain.authoritative and sip:
                        default_ttl = Config.objects.get_config(
                            "default_dns_ttl"
                        )
                        ttl = (
                            dnsrr.address_ttl
                            if dnsrr.address_ttl
                            else domain.ttl
                            if domain.ttl
                            else default_ttl
                        )

                        ip = str(sip.ip)

                        DNSPublication.objects.create_for_config_update(
                            source=f"ip {ip} linked to resource {dnsrr.name} on zone {domain.name}",
                            action=DnsUpdateAction.INSERT,
                            zone=domain.name,
                            label=dnsrr.name,
                            ttl=ttl,
                            rtype="A"
                            if IPAddress(ip).version == 4
                            else "AAAA",
                            answer=ip,
                        )

            return super().add(*args, **kwargs)

        def remove(self, *args, **kwargs):
            dnsrr = self.instance
            domain = dnsrr.domain
            if domain.authoritative and len(args) > 0:
                sip = args[0] if isinstance(args[0], StaticIPAddress) else None
                if sip:
                    default_ttl = Config.objects.get_config("default_dns_ttl")
                    ttl = (
                        dnsrr.address_ttl
                        if dnsrr.address_ttl
                        else domain.ttl
                        if domain.ttl
                        else default_ttl
                    )
                    ip = str(sip.ip)

                    DNSPublication.objects.create_for_config_update(
                        source=f"ip {ip} unlinked from resource {dnsrr.name} on zone {domain.name}",
                        action=DnsUpdateAction.DELETE,
                        zone=domain.name,
                        label=dnsrr.name,
                        ttl=ttl,
                        rtype="A" if IPAddress(ip).version == 4 else "AAAA",
                        answer=ip,
                    )

            return super().remove(*args, **kwargs)

        def set(self, *args, **kwargs):
            if len(args) > 0:
                dnsrr = self.instance
                domain = dnsrr.domain
                default_ttl = Config.objects.get_config("default_dns_ttl")
                ttl = (
                    dnsrr.address_ttl
                    if dnsrr.address_ttl
                    else domain.ttl
                    if domain.ttl
                    else default_ttl
                )
                elements = args[0] if isinstance(args[0], list) else []
                for element in elements:
                    if not isinstance(element, StaticIPAddress):
                        continue
                    if domain.authoritative:
                        ip = str(element.ip)

                        DNSPublication.objects.create_for_config_update(
                            source=f"ip {ip} linked to resource {dnsrr.name} on zone {domain.name}",
                            action=DnsUpdateAction.INSERT,
                            zone=domain.name,
                            label=dnsrr.name,
                            ttl=ttl,
                            rtype="A"
                            if IPAddress(ip).version == 4
                            else "AAAA",
                            answer=ip,
                        )

                return super().set(*args, **kwargs)

    return DNSResourceIPAddressesManager


class DNSResourceIPAddressesDescriptor(ManyToManyDescriptor):
    @cached_property
    def related_manager_cls(self):
        related_model = (
            self.rel.related_model if self.reverse else self.rel.model
        )
        return dnsresource_ip_addresses_manager_factory(
            related_model._default_manager.__class__,
            self.rel,
            reverse=self.reverse,
        )


class DNSResourceIPAddressesField(ManyToManyField):
    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        setattr(
            cls,
            self.name,
            DNSResourceIPAddressesDescriptor(self.remote_field, reverse=False),
        )

    def contribute_to_related_class(self, cls, related):
        super().contribute_to_related_class(cls, related)

        if (
            not self.remote_field.hidden
            and not related.related_model._meta.swapped
        ):
            setattr(
                cls,
                related.get_accessor_name(),
                DNSResourceIPAddressesDescriptor(
                    self.remote_field, reverse=True
                ),
            )


class DNSResource(CleanSave, TimestampedModel):
    """A `DNSResource`.

    :ivar name: The leftmost label for the resource. (No dots.)
    :ivar domain: Which (forward) DNS zone does this resource go in.
    :ivar ip_addresses: many-to-many linkage to `StaticIPAddress`.
    :ivar objects: An instance of the class :class:`DNSResourceManager`.
    """

    class Meta:
        verbose_name = "DNSResource"
        verbose_name_plural = "DNSResources"

    objects = DNSResourceManager()

    # If name is blank or None, then we'll use $IFACE.$NODENAME.$DOMAIN (and
    # $NODENAME.$DOMAIN if this is the pxeboot interface), otherwise we'll use
    # only NAME.$DOMAIN.
    # There can be more than one name=None entry, so unique needs to be False.
    # We detect and reject duplicates in clean()
    # This could be as many as 3 dot-separated labels, because of SRV records.
    name = CharField(
        max_length=191, editable=True, null=True, blank=True, unique=False
    )

    # Different resource types can have different TTL values, though all of the
    # records of a given RRType for a given FQDN "must" have the same TTL.
    # If the DNS zone file has different TTLs for the same RRType on a label,
    # then BIND uses the first one in the file, and logs something similar to:
    #   /etc/bind/maas/zone.maas:25: TTL set to prior TTL (10)
    # We allow this condition to happen so that the user has a hope of changing
    # TTLs for a multi-entry RRset.

    # TTL for any ip_addresses:  non-address TTLs come from DNSData
    address_ttl = PositiveIntegerField(default=None, null=True, blank=True)

    domain = ForeignKey(
        Domain, default=get_default_domain, editable=True, on_delete=PROTECT
    )

    ip_addresses = DNSResourceIPAddressesField(
        StaticIPAddress,
        editable=True,
        blank=True,
    )

    # DNSData model has non-ipaddress entries.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._previous_name = None
        self._previous_domain_id = None

    def __setattr__(self, name, value):
        if (
            hasattr(self, f"_previous_{name}")
            and getattr(self, name) is not None
        ):
            setattr(self, f"_preivous_{name}", getattr(self, name))
        super().__setattr__(name, value)

    def __unicode__(self):
        return "name=%s" % self.get_name()

    def __str__(self):
        return "name=%s" % self.get_name()

    @property
    def fqdn(self):
        """Fully qualified domain name for this DNSResource.

        Return the FQDN for this DNSResource.
        """
        if self.name == "@":
            return self.domain.name
        else:
            return f"{self.name}.{self.domain.name}"

    def has_static_ip(self):
        return self.ip_addresses.exclude(
            alloc_type=IPADDRESS_TYPE.DISCOVERED
        ).exists()

    def get_addresses(self):
        """Return all addresses associated with this FQDN."""
        # Since Node.hostname is unique, this will be at most 1 node.
        node = Node.objects.filter(
            hostname=self.name, domain_id=self.domain_id
        )
        ips = [ip.get_ip() for ip in self.ip_addresses.all()]
        if node.exists():
            ips += node[0].static_ip_addresses()
        return ips

    def get_name(self):
        """Return the name of the dnsresource."""
        return self.name

    def clean(self, *args, **kwargs):
        # Avoid recursive imports.
        from maasserver.models.dnsdata import DNSData

        # make sure that we have a domain
        if self.domain is None or self.domain == "":
            self.domain = Domain.objects.get_default_domain()
        # if we have a name, make sure that it is unique in our dns zone.
        if self.id is None and self.name is not None and self.name != "":
            rrset = DNSResource.objects.filter(
                name=self.name, domain=self.domain
            )
            if rrset.exists():
                raise ValidationError(
                    "Labels must be unique within their zone."
                )
        # If we have an ip addresses, then we need to have a valid name.
        # TXT records don't require that we have much at all.
        if self.id is not None and self.ip_addresses.exists():
            validate_dnsresource_name(self.name, "A")
            # This path could be followed if the user is adding a USER_RESERVED
            # ip address, where the FQDN already has a CNAME assigned to it.
            # Node.fqdn takes a different path, and should win when it comes to
            # DNS generation.
            cname_exists = DNSData.objects.filter(
                dnsresource_id=self.id, rrtype="CNAME"
            ).exists()
            if cname_exists:
                raise ValidationError("Cannot add address: CNAME present.")
        super().clean(*args, **kwargs)

    def render_json(self, system_id):
        """Render json.  System_id is the system_id for the node, if one
        exists.  Addresses are rendered in the calling function."""
        return sorted(
            {
                "hostname": self.name,
                "ttl": data.ttl,
                "rrtype": data.rrtype,
                "rrdata": data.rrdata,
                "system_id": system_id,
            }
            for data in self.dnsdata_set.all()
        )

    def delete(self, *args, **kwargs):
        # delete all the user reserved static ip addresses not linked to any interface
        for ip in self.ip_addresses.all():
            if ip.is_safe_to_delete():
                ip.delete()

        if self.domain.authoritative:
            DNSPublication.objects.create_for_config_update(
                source=f"zone {self.domain.name} removed resource {self.name}",
                action=DnsUpdateAction.DELETE,
                label=self.name,
                rtype="A",
            )

        return super().delete(*args, **kwargs)

    def save(self, *args, **kwargs):
        if self.domain.authoritative or self._previous_domain_id is not None:
            if self.id is None:
                DNSPublication.objects.create_for_config_update(
                    source=f"zone {self.domain.name} added resource {self.name}",
                    action=DnsUpdateAction.INSERT_NAME,
                    label=self.name,
                    rtype="A",
                    zone=self.domain,
                )
            else:
                if (
                    self._previous_domain_id is not None
                    and self._previous_domain_id != self.domain_id
                ):
                    old_domain = Domain.objects.get(
                        id=self._previous_domain_id
                    )

                    if old_domain.authoritative:
                        DNSPublication.objects.create_for_config_update(
                            source=f"zone {old_domain.name} removed resource {self._previous_name if self._previous_name else self.name}",
                            action=DnsUpdateAction.DELETE,
                            label=self._previous_name
                            if self._previous_name
                            else self.name,
                            rtype="A",
                            zone=old_domain.name,
                        )
                    if self.domain.authoritative:
                        DNSPublication.objects.create_for_config_update(
                            source=f"zone {self.domain.name} added resource {self.name}",
                            action=DnsUpdateAction.INSERT_NAME,
                            label=self.name,
                            rtype="A",
                            zone=self.domain,
                        )
                else:
                    if (
                        self._previous_name
                        and self._previous_name != self.name
                    ):
                        DNSPublication.objects.create_for_config_update(
                            source=f"zone {self.domain.name} removed resource {self._previous_name}",
                            action=DnsUpdateAction.DELETE,
                            label=self._previous_name,
                            rtype="A",
                        )
                        DNSPublication.objects.create_for_config_update(
                            source=f"zone {self.domain.name} added resource {self.name}",
                            action=DnsUpdateAction.INSERT_NAME,
                            label=self.name,
                            rtype="A",
                            ttl=self.address_ttl,
                        )
                    else:
                        DNSPublication.objects.create_for_config_update(
                            source=f"zone {self.domain.name} updated resource {self.name}",
                            action=DnsUpdateAction.UPDATE,
                            label=self.name,
                            rtype="A",
                            ttl=self.address_ttl,
                        )
        return super().save(*args, **kwargs)
