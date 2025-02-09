# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Model definition for a `Discovery` (a discovered network device)."""

from django.db.models import (
    BooleanField,
    CharField,
    DateTimeField,
    DO_NOTHING,
    ForeignKey,
    GenericIPAddressField,
    IntegerField,
    Manager,
    Model,
    TextField,
)
from django.db.models.query import QuerySet

from maasserver.fields import CIDRField, DomainNameField, MAC_VALIDATOR
from maasserver.utils.orm import MAASQueriesMixin
from provisioningserver.logger import get_maas_logger
from provisioningserver.utils.network import get_mac_organization

maaslog = get_maas_logger("discovery")


class DiscoveryQueriesMixin(MAASQueriesMixin):
    def get_specifiers_q(self, specifiers, separator=":", **kwargs):
        # This dict is used by the constraints code to identify objects
        # with particular properties. Please note that changing the keys here
        # can impact backward compatibility, so use caution.
        specifier_types = {
            None: "__discovery_id",
            "ip": "__ip",
            "mac": "__mac_address",
        }
        return super().get_specifiers_q(
            specifiers,
            specifier_types=specifier_types,
            separator=separator,
            **kwargs,
        )

    def by_unknown_mac(self):
        """Returns a `QuerySet` of discoveries which have a MAC that is unknown
        to MAAS. (That is, is not associated with any known Interface.)
        """
        # Circular imports
        from maasserver.models import Interface

        known_macs = Interface.objects.values_list(
            "mac_address", flat=True
        ).distinct()
        return self.exclude(mac_address__in=known_macs)

    def by_unknown_ip(self):
        """Returns a `QuerySet` of discoveries which have an IP that is unknown
        to MAAS. (That is, is not associated with any known StaticIPAddress.)
        """
        # Circular imports
        from maasserver.models import StaticIPAddress

        known_ips = StaticIPAddress.objects.exclude(
            ip__isnull=True
        ).values_list("ip", flat=True)
        return self.exclude(ip__in=known_ips)

    def by_unknown_ip_and_mac(self):
        """Returns a `QuerySet` of discoveries which have a MAC and IP
        address which are *both* unknown to MAAS. (That is, is not associated
        with any known Interface and StaticIPAddress, respectively.)

        This could happen if a known IP address is seen from an unexpected MAC,
        or if a known MAC address is seen using an unexpected IP. We may want
        to filter these types of irregularities from the user, so that
        unexpected devices do not show up in their discovered devices list.
        However, we may wish to surface the discoveries filtered by this query
        in another way.
        """
        return self.by_unknown_mac().by_unknown_ip()


class DiscoveryQuerySet(DiscoveryQueriesMixin, QuerySet):
    """Custom QuerySet which mixes in some additional queries specific to
    subnets. This needs to be a mixin because an identical method is needed on
    both the Manager and all QuerySets which result from calling the manager.
    """


class DiscoveryManager(Manager, DiscoveryQueriesMixin):
    """A utility to manage collections of Discoverys."""

    def get_queryset(self):
        queryset = DiscoveryQuerySet(self.model, using=self._db)
        return queryset

    def get_discovery_or_404(self, specifiers):
        """Fetch a `Discovery` by its ID or specifiers.

        :param specifiers: The discovery specifiers.
        :type specifiers: str
        :raises: django.http.Http404_,
            :class:`maasserver.exceptions.PermissionDenied`.

        .. _django.http.Http404: https://
           docs.djangoproject.com/en/dev/topics/http/views/
           #the-http404-exception
        """
        discovery = self.get_object_by_specifiers_or_raise(specifiers)
        return discovery

    def clear(self, user=None, all=False, mdns=False, neighbours=False):
        """Deletes discoveries of the specified type(s).

        :param all: Deletes all discovery data.
        :param mdns: Deletes mDNS entries.
        :param neighbours: Deletes neighbour entries.
        """
        # Circular imports.
        from maasserver.models import MDNS, Neighbour

        if True not in (all, mdns, neighbours):
            return
        if mdns or all:
            MDNS.objects.all().delete()
            what = "mDNS"
        if neighbours or all:
            Neighbour.objects.all().delete()
            what = "neighbour"
        if all:
            what = "mDNS and neighbour"
        maaslog.info(
            "%s all %s entries."
            % (
                (
                    "Cleared"
                    if user is None
                    else "User '%s' cleared" % (user.username)
                ),
                what,
            )
        )

    def delete_by_mac_and_ip(self, ip, mac, user=None):
        # Circular imports.
        from maasserver.models import MDNS, Neighbour, RDNS

        delete_result = Neighbour.objects.filter(
            ip=ip, mac_address=mac
        ).delete()
        MDNS.objects.filter(ip=ip).delete()
        RDNS.objects.filter(ip=ip).delete()
        if delete_result[0] >= 1:
            maaslog.info(
                "%s%s."
                % (
                    (
                        "Cleared"
                        if user is None
                        else "User '%s' cleared" % (user.username)
                    ),
                    f" neighbour entry: {ip} ({mac})",
                )
            )
        return delete_result


class Discovery(Model):
    """A `Discovery` object represents the combined data for a network entity
    that MAAS believes has been discovered.

    Note that this class is backed by the `maasserver_discovery` view. Any
    updates to this model must be reflected in `maasserver/dbviews.py` under
    the `maasserver_discovery` view.
    """

    class Meta:
        verbose_name = "Discovery"
        verbose_name_plural = "Discoveries"
        # this is a view-backed model
        managed = False

    def __str__(self):
        return "<Discovery: {} at {} via {}>".format(
            self.ip,
            self.last_seen,
            self.observer_interface.get_log_string(),
        )

    discovery_id = CharField(
        max_length=256, editable=False, null=True, blank=False, unique=True
    )

    neighbour = ForeignKey(
        "Neighbour",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=DO_NOTHING,
    )

    # Observed IP address.
    ip = GenericIPAddressField(
        unique=False,
        null=True,
        editable=False,
        blank=True,
        default=None,
        verbose_name="IP",
    )

    mac_address = TextField(
        unique=False,
        null=True,
        blank=True,
        validators=[MAC_VALIDATOR],
    )

    first_seen = DateTimeField(editable=False)

    last_seen = DateTimeField(editable=False)

    mdns = ForeignKey(
        "MDNS",
        unique=False,
        blank=True,
        null=True,
        editable=False,
        on_delete=DO_NOTHING,
    )

    # Hostname observed from mDNS-browse.
    hostname = CharField(
        max_length=256, editable=False, null=True, blank=False, unique=False
    )

    observer = ForeignKey(
        "Node",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=DO_NOTHING,
    )

    observer_system_id = CharField(max_length=41, unique=False, editable=False)

    # The hostname of the node that made the discovery.
    observer_hostname = DomainNameField(
        max_length=256, editable=False, null=True, blank=False, unique=False
    )

    # Rack interface the discovery was observed on.
    observer_interface = ForeignKey(
        "Interface",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=DO_NOTHING,
    )

    observer_interface_name = CharField(
        blank=False, editable=False, max_length=255
    )

    fabric = ForeignKey(
        "Fabric",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=DO_NOTHING,
    )

    fabric_name = CharField(
        max_length=256, editable=False, null=True, blank=True, unique=False
    )

    vlan = ForeignKey(
        "VLAN",
        unique=False,
        blank=False,
        null=False,
        editable=False,
        on_delete=DO_NOTHING,
    )

    vid = IntegerField(null=True, blank=True)

    # These will only be non-NULL if we found a related Subnet.
    subnet = ForeignKey(
        "Subnet",
        unique=False,
        blank=True,
        null=True,
        editable=False,
        on_delete=DO_NOTHING,
    )

    subnet_cidr = CIDRField(
        blank=True, unique=False, editable=False, null=True
    )

    is_external_dhcp = BooleanField(
        blank=True, unique=False, editable=False, null=True
    )

    objects = DiscoveryManager()

    @property
    def mac_organization(self):
        return get_mac_organization(str(self.mac_address))
